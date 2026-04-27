# BRAIN 3.0 — AI-powered personal operating system for ADHD
# Copyright (C) 2026 L (WilliM233)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Tests for [2C-05] FCM dispatch wiring.

Exercises the ``pending → delivered`` side-effect on both the
interactive PATCH path and the delivery promoter path. The FCM client
itself is mocked — no live network hits in CI.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models import AppDevice, NotificationQueue
from app.services import delivery, delivery_promoter, fcm
from app.services.delivery import build_fcm_payload, dispatch_push
from app.services.fcm import FcmResult, FcmStatus


@dataclass
class _RecordedCall:
    """Captured arguments from a mocked ``send_notification_to_device`` call."""

    fcm_token: str
    payload: dict


class _FcmRecorder:
    """List-like recorder of FCM send calls plus a queue of canned results.

    Tests append :class:`FcmResult` instances to ``next_results`` to control
    the response of subsequent ``send_notification_to_device`` calls. With an
    empty queue, each call returns SENT.
    """

    def __init__(self) -> None:
        self.calls: list[_RecordedCall] = []
        self.next_results: list[FcmResult] = []

    def __iter__(self):
        return iter(self.calls)

    def __len__(self) -> int:
        return len(self.calls)

    def __getitem__(self, idx: int) -> _RecordedCall:
        return self.calls[idx]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return self.calls == other
        return NotImplemented


@pytest.fixture
def mock_fcm_client(monkeypatch):
    """Replace the FCM client with a recorder and return it.

    Default behaviour: every call returns SENT. Tests that need an error
    can append a result to ``mock_fcm_client.next_results``.
    """
    recorder = _FcmRecorder()

    def _send(fcm_token: str, payload: dict) -> FcmResult:
        recorder.calls.append(_RecordedCall(fcm_token=fcm_token, payload=payload))
        if recorder.next_results:
            return recorder.next_results.pop(0)
        return FcmResult(status=FcmStatus.SENT, http_status=200)

    monkeypatch.setattr(fcm, "send_notification_to_device", _send)
    monkeypatch.setattr(
        delivery.fcm, "send_notification_to_device", _send,
    )

    return recorder


def _make_pending_notification(
    db,
    *,
    notification_type: str = "habit_nudge",
    canned_responses: list[str] | None = None,
    rule_id: uuid.UUID | None = None,
) -> NotificationQueue:
    scheduled_at = datetime.now(tz=UTC) - timedelta(minutes=5)
    row = NotificationQueue(
        notification_type=notification_type,
        delivery_type="notification",
        status="pending",
        scheduled_at=scheduled_at,
        scheduled_date=scheduled_at.date(),
        target_entity_type="habit",
        target_entity_id=uuid.uuid4(),
        message="Time to stretch!",
        canned_responses=canned_responses,
        scheduled_by="system",
        rule_id=rule_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _register_device(db, *, fcm_token: str, platform: str = "android") -> AppDevice:
    device = AppDevice(fcm_token=fcm_token, platform=platform)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


# ---------------------------------------------------------------------------
# build_fcm_payload — payload shape contract with the companion app
# ---------------------------------------------------------------------------


class TestBuildFcmPayload:
    """The data-only payload shape is the contract with [2C-06]."""

    def test_payload_uses_data_only_with_high_priority(self, db) -> None:
        notif = _make_pending_notification(
            db, canned_responses=["yes", "no", "snooze"],
        )
        payload = build_fcm_payload(notif)
        assert "notification" not in payload, (
            "FCM payload must be data-only; the notification field would let "
            "Android render a non-actionable toast and the plugin would never "
            "see the data."
        )
        assert payload["android"] == {"priority": "HIGH"}
        data = payload["data"]
        assert data["notification_id"] == str(notif.id)
        assert data["notification_type"] == "habit_nudge"
        assert data["message"] == "Time to stretch!"
        assert json.loads(data["canned_responses"]) == ["yes", "no", "snooze"]
        assert data["scheduled_date"] == notif.scheduled_date.isoformat()
        assert data["rule_id"] == ""

    def test_null_canned_responses_serialises_as_empty_array(self, db) -> None:
        notif = _make_pending_notification(db, canned_responses=None)
        payload = build_fcm_payload(notif)
        assert json.loads(payload["data"]["canned_responses"]) == []

    def test_data_values_are_all_strings(self, db) -> None:
        """FCM v1 ``data`` is ``map<string, string>`` — coercion is mandatory."""
        notif = _make_pending_notification(db)
        data = build_fcm_payload(notif)["data"]
        for key, value in data.items():
            assert isinstance(value, str), (
                f"data[{key!r}] is {type(value).__name__}, must be str"
            )


# ---------------------------------------------------------------------------
# dispatch_push — broadcast + invalidation cleanup
# ---------------------------------------------------------------------------


class TestDispatchPush:
    """Direct tests of ``dispatch_push`` against a fixture device set."""

    def test_no_devices_no_calls(self, db, mock_fcm_client) -> None:
        notif = _make_pending_notification(db)
        sent = dispatch_push(notif, db)
        assert sent == 0
        assert mock_fcm_client == []

    def test_broadcasts_to_every_registered_device(
        self, db, mock_fcm_client,
    ) -> None:
        _register_device(db, fcm_token="token-1")
        _register_device(db, fcm_token="token-2")
        _register_device(db, fcm_token="token-3")

        notif = _make_pending_notification(db)
        sent = dispatch_push(notif, db)

        assert sent == 3
        assert {c.fcm_token for c in mock_fcm_client} == {
            "token-1", "token-2", "token-3",
        }
        for call in mock_fcm_client:
            assert call.payload["android"]["priority"] == "HIGH"
            assert call.payload["data"]["notification_id"] == str(notif.id)

    def test_unregistered_token_removes_device(
        self, db, mock_fcm_client,
    ) -> None:
        _register_device(db, fcm_token="good-token")
        _register_device(db, fcm_token="dead-token")

        # First call → SENT (good-token), second → UNREGISTERED (dead-token).
        # Insertion order in app_devices is deterministic by registered_at.
        mock_fcm_client.next_results.extend([
            FcmResult(status=FcmStatus.SENT, http_status=200),
            FcmResult(
                status=FcmStatus.UNREGISTERED,
                http_status=404,
                error_code="UNREGISTERED",
            ),
        ])

        notif = _make_pending_notification(db)
        sent = dispatch_push(notif, db)

        assert sent == 1
        # The dead token row is gone; the live one survives.
        remaining_tokens = {
            row.fcm_token for row in db.query(AppDevice).all()
        }
        assert remaining_tokens == {"good-token"}

    def test_invalid_argument_token_removes_device(
        self, db, mock_fcm_client,
    ) -> None:
        _register_device(db, fcm_token="bad-token")
        mock_fcm_client.next_results.append(
            FcmResult(
                status=FcmStatus.INVALID_ARGUMENT,
                http_status=400,
                error_code="INVALID_ARGUMENT",
            ),
        )
        notif = _make_pending_notification(db)
        dispatch_push(notif, db)
        assert db.query(AppDevice).count() == 0

    def test_transient_error_keeps_device(self, db, mock_fcm_client) -> None:
        _register_device(db, fcm_token="rate-limited")
        mock_fcm_client.next_results.append(
            FcmResult(status=FcmStatus.RATE_LIMITED, http_status=429),
        )
        notif = _make_pending_notification(db)
        dispatch_push(notif, db)
        # Rate-limited tokens stay registered — only UNREGISTERED /
        # INVALID_ARGUMENT trigger removal.
        assert db.query(AppDevice).count() == 1


# ---------------------------------------------------------------------------
# PATCH integration — pending → delivered triggers FCM dispatch
# ---------------------------------------------------------------------------


class TestPatchHandlerDispatch:
    """``PATCH /api/notifications/{id}`` with status=delivered fires FCM."""

    def test_patch_to_delivered_invokes_fcm_for_each_device(
        self, client: TestClient, db, mock_fcm_client,
    ) -> None:
        _register_device(db, fcm_token="patch-token-1")
        _register_device(db, fcm_token="patch-token-2")
        notif = _make_pending_notification(db)

        resp = client.patch(
            f"/api/notifications/{notif.id}",
            json={"status": "delivered"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"

        assert {c.fcm_token for c in mock_fcm_client} == {
            "patch-token-1", "patch-token-2",
        }
        for call in mock_fcm_client:
            data = call.payload["data"]
            assert data["notification_id"] == str(notif.id)
            assert data["notification_type"] == "habit_nudge"
            assert data["message"] == "Time to stretch!"

    def test_patch_to_other_field_does_not_dispatch(
        self, client: TestClient, db, mock_fcm_client,
    ) -> None:
        _register_device(db, fcm_token="should-not-fire")
        notif = _make_pending_notification(db)

        resp = client.patch(
            f"/api/notifications/{notif.id}",
            json={"message": "Updated copy"},
        )
        assert resp.status_code == 200
        assert mock_fcm_client == []

    def test_patch_dispatch_failure_does_not_break_response(
        self, client: TestClient, db, monkeypatch,
    ) -> None:
        """A raising dispatch_push is logged, not surfaced as a 500."""
        from app.routers import notification as notif_router

        def _boom(*_args, **_kwargs):
            raise RuntimeError("FCM service unavailable")

        monkeypatch.setattr(notif_router, "dispatch_push", _boom)

        notif = _make_pending_notification(db)
        resp = client.patch(
            f"/api/notifications/{notif.id}",
            json={"status": "delivered"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"


# ---------------------------------------------------------------------------
# Promoter integration — AC #1 carry-forward from [2C-05a] PR #212 D-18
# ---------------------------------------------------------------------------


class TestPromoterDispatchesFcm:
    """The delivery promoter must invoke FCM dispatch on transition.

    Per [2C-05] AC #1 ("verify FCM dispatch has been invoked"), originally
    deferred from [2C-05a] PR #212 (deviation D-18) because the dispatch
    path did not exist yet. This ticket inherits that obligation: when
    the promoter promotes a row from ``pending`` to ``delivered``, it
    must trigger ``dispatch_push`` exactly as the PATCH handler does.
    """

    def test_promoter_calls_fcm_for_each_promoted_row(
        self, db, mock_fcm_client,
    ) -> None:
        _register_device(db, fcm_token="promoter-token")

        notif = _make_pending_notification(db)

        promoted = delivery_promoter.promote_due_notifications(db)

        assert promoted == 1
        assert len(mock_fcm_client) == 1
        call = mock_fcm_client[0]
        assert call.fcm_token == "promoter-token"
        assert call.payload["data"]["notification_id"] == str(notif.id)

    def test_promoter_dispatch_failure_does_not_block_promotion(
        self, db, monkeypatch,
    ) -> None:
        """A raising dispatch_push is logged but does not stop the row promotion."""

        def _boom(*_args, **_kwargs):
            raise RuntimeError("dispatch went sideways")

        monkeypatch.setattr(delivery_promoter, "dispatch_push", _boom)

        notif = _make_pending_notification(db)
        promoted = delivery_promoter.promote_due_notifications(db)

        assert promoted == 1
        db.refresh(notif)
        assert notif.status == "delivered"

    def test_promoter_skips_dispatch_when_no_devices(
        self, db, mock_fcm_client,
    ) -> None:
        """No devices registered → promotion still happens, no FCM calls."""
        notif = _make_pending_notification(db)
        promoted = delivery_promoter.promote_due_notifications(db)

        assert promoted == 1
        db.refresh(notif)
        assert notif.status == "delivered"
        assert mock_fcm_client == []
