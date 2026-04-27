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

"""Tests for [2B-05] response expiry windows and notification retention.

Updated by [2C-04] to assert v0.9 §Q4 EXPIRY_DEFAULTS values, the
``time_block_reminder`` block_duration floor, and the ``routine_checklist``
EOD-local boundary.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.config import settings
from app.models import NotificationQueue
from app.services.notification_defaults import (
    EXPIRY_DEFAULTS,
    RETENTION_DAYS,
    calculate_expires_at,
    get_expired_notifications,
    get_retention_candidates,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_URL = "/api/notifications"

NOTIFICATION_TYPES = [
    "habit_nudge",
    "routine_checklist",
    "checkin_prompt",
    "time_block_reminder",
    "deadline_event_alert",
    "pattern_observation",
    "stale_work_nudge",
]


def make_notification(client, **overrides) -> dict:
    """Create a notification via the API and return the response JSON."""
    data = {
        "notification_type": "habit_nudge",
        "delivery_type": "notification",
        "scheduled_at": "2026-04-15T09:00:00Z",
        "scheduled_date": "2026-04-15",
        "target_entity_type": "habit",
        "target_entity_id": str(uuid.uuid4()),
        "message": "Time to stretch!",
        "scheduled_by": "system",
        **overrides,
    }
    resp = client.post(BASE_URL, json=data)
    assert resp.status_code == 201, resp.text
    return resp.json()


def deliver(client, notification_id: str) -> dict:
    """Transition a notification to delivered via PATCH."""
    resp = client.patch(
        f"{BASE_URL}/{notification_id}", json={"status": "delivered"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def make_db_notification(db, **overrides) -> NotificationQueue:
    """Insert a NotificationQueue row directly for query-level tests."""
    scheduled_at = overrides.get("scheduled_at", datetime(2026, 4, 15, 9, 0, tzinfo=UTC))
    data = {
        "notification_type": "habit_nudge",
        "delivery_type": "notification",
        "status": "pending",
        "scheduled_at": scheduled_at,
        "scheduled_date": scheduled_at.date(),
        "target_entity_type": "habit",
        "target_entity_id": uuid.uuid4(),
        "message": "Test notification",
        "scheduled_by": "system",
        **overrides,
    }
    notif = NotificationQueue(**data)
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


# ===========================================================================
# Unit tests — EXPIRY_DEFAULTS constant
# ===========================================================================


class TestExpiryDefaults:
    """EXPIRY_DEFAULTS covers all 7 notification types with correct values."""

    def test_all_types_present(self):
        for ntype in NOTIFICATION_TYPES:
            assert ntype in EXPIRY_DEFAULTS

    def test_no_extra_types(self):
        assert set(EXPIRY_DEFAULTS.keys()) == set(NOTIFICATION_TYPES)

    def test_habit_nudge(self):
        assert EXPIRY_DEFAULTS["habit_nudge"] == timedelta(hours=4)

    def test_routine_checklist_fallback(self):
        # Fallback when scheduled_date is missing; the live path resolves
        # to EOD-local — see TestRoutineChecklistEOD.
        assert EXPIRY_DEFAULTS["routine_checklist"] == timedelta(hours=4)

    def test_checkin_prompt(self):
        assert EXPIRY_DEFAULTS["checkin_prompt"] == timedelta(hours=2)

    def test_time_block_reminder(self):
        # 30m default; floored further by block_duration when supplied —
        # see TestTimeBlockFloor.
        assert EXPIRY_DEFAULTS["time_block_reminder"] == timedelta(minutes=30)

    def test_deadline_event_alert(self):
        assert EXPIRY_DEFAULTS["deadline_event_alert"] == timedelta(hours=0)

    def test_pattern_observation(self):
        assert EXPIRY_DEFAULTS["pattern_observation"] == timedelta(hours=48)

    def test_stale_work_nudge(self):
        assert EXPIRY_DEFAULTS["stale_work_nudge"] == timedelta(hours=24)


# ===========================================================================
# Unit tests — RETENTION_DAYS constant
# ===========================================================================


class TestRetentionDays:

    def test_value(self):
        assert RETENTION_DAYS == 90


# ===========================================================================
# Unit tests — calculate_expires_at
# ===========================================================================


class TestCalculateExpiresAt:
    """Expiry calculation logic for each notification type."""

    DELIVERED_AT = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)

    @pytest.mark.parametrize("ntype", [
        t for t in NOTIFICATION_TYPES if t != "deadline_event_alert"
    ])
    def test_applies_type_default(self, ntype):
        result = calculate_expires_at(ntype, self.DELIVERED_AT)
        assert result == self.DELIVERED_AT + EXPIRY_DEFAULTS[ntype]

    def test_deadline_event_alert_falls_back_to_24h(self):
        """deadline_event_alert with no override → 24h fallback."""
        result = calculate_expires_at(
            "deadline_event_alert", self.DELIVERED_AT,
        )
        assert result == self.DELIVERED_AT + timedelta(hours=24)

    def test_preserves_existing_expires_at(self):
        """Per-notification override is not overwritten."""
        override = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
        result = calculate_expires_at(
            "habit_nudge", self.DELIVERED_AT, existing_expires_at=override,
        )
        assert result == override

    def test_preserves_override_for_deadline_event_alert(self):
        """deadline_event_alert with explicit override keeps it."""
        override = datetime(2026, 4, 15, 17, 0, tzinfo=UTC)
        result = calculate_expires_at(
            "deadline_event_alert", self.DELIVERED_AT,
            existing_expires_at=override,
        )
        assert result == override

    def test_unknown_type_returns_none(self):
        result = calculate_expires_at("nonexistent", self.DELIVERED_AT)
        assert result is None

    # Edge cases

    def test_habit_nudge_exact_calculation(self):
        result = calculate_expires_at("habit_nudge", self.DELIVERED_AT)
        assert result == datetime(2026, 4, 15, 14, 0, tzinfo=UTC)

    def test_time_block_reminder_exact_calculation(self):
        # No block_duration supplied → 30m default.
        result = calculate_expires_at("time_block_reminder", self.DELIVERED_AT)
        assert result == datetime(2026, 4, 15, 10, 30, tzinfo=UTC)

    def test_override_in_past_still_preserved(self):
        """Even a past override is preserved — the caller decides validity."""
        past = datetime(2026, 4, 14, 0, 0, tzinfo=UTC)
        result = calculate_expires_at(
            "habit_nudge", self.DELIVERED_AT, existing_expires_at=past,
        )
        assert result == past


# ===========================================================================
# Unit tests — time_block_reminder block_duration floor
# ===========================================================================


class TestTimeBlockFloor:
    """time_block_reminder is floored by block_duration when supplied."""

    DELIVERED_AT = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)

    def test_block_duration_under_floor_wins(self):
        """block_duration < 30m → expiry is delivered_at + block_duration."""
        result = calculate_expires_at(
            "time_block_reminder",
            self.DELIVERED_AT,
            block_duration=timedelta(minutes=10),
        )
        assert result == self.DELIVERED_AT + timedelta(minutes=10)

    def test_block_duration_over_floor_uses_floor(self):
        """block_duration > 30m → expiry is delivered_at + 30m."""
        result = calculate_expires_at(
            "time_block_reminder",
            self.DELIVERED_AT,
            block_duration=timedelta(hours=2),
        )
        assert result == self.DELIVERED_AT + timedelta(minutes=30)

    def test_block_duration_equal_floor(self):
        """block_duration == 30m → expiry is delivered_at + 30m."""
        result = calculate_expires_at(
            "time_block_reminder",
            self.DELIVERED_AT,
            block_duration=timedelta(minutes=30),
        )
        assert result == self.DELIVERED_AT + timedelta(minutes=30)

    def test_no_block_duration_uses_default(self):
        """block_duration omitted → expiry is delivered_at + 30m."""
        result = calculate_expires_at("time_block_reminder", self.DELIVERED_AT)
        assert result == self.DELIVERED_AT + timedelta(minutes=30)

    def test_block_duration_ignored_for_other_types(self):
        """block_duration only floors time_block_reminder; other types ignore it."""
        result = calculate_expires_at(
            "habit_nudge",
            self.DELIVERED_AT,
            block_duration=timedelta(minutes=10),
        )
        assert result == self.DELIVERED_AT + timedelta(hours=4)


# ===========================================================================
# Unit tests — routine_checklist EOD-local
# ===========================================================================


class TestRoutineChecklistEOD:
    """routine_checklist resolves to midnight at start of next day in SERVER_TZ."""

    SCHEDULED_DATE = date(2026, 4, 20)

    def test_eod_local_late_evening(self):
        """Spec example (adapted to SERVER_TZ=America/Chicago): scheduled
        2026-04-20, delivered 22:15 local → expires 2026-04-21T00:00 local.
        Confirms expiry does NOT cross into the next day via delivered_at + 4h.
        """
        tz = ZoneInfo("America/Chicago")
        # Pre-condition for the test's intent: SERVER_TZ is Chicago.
        assert settings.SERVER_TZ == "America/Chicago"

        delivered_at = datetime(2026, 4, 20, 22, 15, tzinfo=tz)
        result = calculate_expires_at(
            "routine_checklist",
            delivered_at,
            scheduled_date=self.SCHEDULED_DATE,
        )
        expected = datetime(2026, 4, 21, 0, 0, tzinfo=tz)
        assert result == expected
        # Sanity: NOT the old delivered_at + 4h behavior (which would be
        # 2026-04-21T02:15 local — well past midnight).
        assert result != delivered_at + timedelta(hours=4)

    def test_eod_local_early_morning(self):
        """Delivered early on scheduled day → expires at next day's midnight."""
        tz = ZoneInfo("America/Chicago")
        delivered_at = datetime(2026, 4, 20, 6, 0, tzinfo=tz)
        result = calculate_expires_at(
            "routine_checklist",
            delivered_at,
            scheduled_date=self.SCHEDULED_DATE,
        )
        assert result == datetime(2026, 4, 21, 0, 0, tzinfo=tz)

    def test_eod_local_uses_server_tz_setting(self, monkeypatch):
        """The boundary is computed in settings.SERVER_TZ, not UTC."""
        monkeypatch.setattr(settings, "SERVER_TZ", "America/New_York")
        tz = ZoneInfo("America/New_York")
        delivered_at = datetime(2026, 4, 20, 22, 15, tzinfo=tz)
        result = calculate_expires_at(
            "routine_checklist",
            delivered_at,
            scheduled_date=self.SCHEDULED_DATE,
        )
        assert result == datetime(2026, 4, 21, 0, 0, tzinfo=tz)

    def test_falls_back_to_default_when_scheduled_date_missing(self):
        """Without scheduled_date, falls back to delivered_at + 4h default."""
        delivered_at = datetime(2026, 4, 20, 22, 15, tzinfo=UTC)
        result = calculate_expires_at("routine_checklist", delivered_at)
        assert result == delivered_at + timedelta(hours=4)


# ===========================================================================
# Query tests — get_expired_notifications
# ===========================================================================


class TestGetExpiredNotifications:
    """Query for delivered notifications past their expiry window."""

    def test_returns_delivered_past_expiry(self, db):
        notif = make_db_notification(
            db,
            status="delivered",
            expires_at=datetime(2026, 4, 10, 0, 0, tzinfo=UTC),  # in the past
        )
        result = get_expired_notifications(db)
        assert len(result) == 1
        assert result[0].id == notif.id

    def test_excludes_delivered_not_yet_expired(self, db):
        make_db_notification(
            db,
            status="delivered",
            expires_at=datetime(2099, 1, 1, 0, 0, tzinfo=UTC),  # far future
        )
        result = get_expired_notifications(db)
        assert len(result) == 0

    def test_excludes_delivered_without_expires_at(self, db):
        make_db_notification(db, status="delivered", expires_at=None)
        result = get_expired_notifications(db)
        assert len(result) == 0

    def test_excludes_pending_past_expiry(self, db):
        make_db_notification(
            db,
            status="pending",
            expires_at=datetime(2026, 4, 10, 0, 0, tzinfo=UTC),
        )
        result = get_expired_notifications(db)
        assert len(result) == 0

    def test_excludes_responded(self, db):
        make_db_notification(
            db,
            status="responded",
            expires_at=datetime(2026, 4, 10, 0, 0, tzinfo=UTC),
        )
        result = get_expired_notifications(db)
        assert len(result) == 0

    def test_excludes_already_expired_status(self, db):
        make_db_notification(
            db,
            status="expired",
            expires_at=datetime(2026, 4, 10, 0, 0, tzinfo=UTC),
        )
        result = get_expired_notifications(db)
        assert len(result) == 0

    def test_multiple_expired(self, db):
        for _ in range(3):
            make_db_notification(
                db,
                status="delivered",
                expires_at=datetime(2026, 4, 10, 0, 0, tzinfo=UTC),
            )
        make_db_notification(
            db,
            status="delivered",
            expires_at=datetime(2099, 1, 1, 0, 0, tzinfo=UTC),
        )
        result = get_expired_notifications(db)
        assert len(result) == 3


# ===========================================================================
# Query tests — get_retention_candidates
# ===========================================================================


class TestGetRetentionCandidates:
    """Query for terminal-state notifications past the retention window."""

    def test_returns_responded_past_retention(self, db):
        notif = make_db_notification(
            db,
            status="responded",
            updated_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        )
        result = get_retention_candidates(db)
        assert len(result) == 1
        assert result[0].id == notif.id

    def test_returns_expired_past_retention(self, db):
        notif = make_db_notification(
            db,
            status="expired",
            updated_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        )
        result = get_retention_candidates(db)
        assert len(result) == 1
        assert result[0].id == notif.id

    def test_excludes_pending(self, db):
        make_db_notification(
            db,
            status="pending",
            updated_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        )
        result = get_retention_candidates(db)
        assert len(result) == 0

    def test_excludes_delivered(self, db):
        make_db_notification(
            db,
            status="delivered",
            updated_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        )
        result = get_retention_candidates(db)
        assert len(result) == 0

    def test_excludes_recent_responded(self, db):
        make_db_notification(
            db,
            status="responded",
            updated_at=datetime.now(tz=UTC),
        )
        result = get_retention_candidates(db)
        assert len(result) == 0

    def test_custom_retention_days(self, db):
        make_db_notification(
            db,
            status="responded",
            updated_at=datetime.now(tz=UTC) - timedelta(days=31),
        )
        # Default 90 days — shouldn't match
        assert len(get_retention_candidates(db)) == 0
        # Custom 30 days — should match
        assert len(get_retention_candidates(db, retention_days=30)) == 1

    def test_boundary_recent_side_excluded(self, db):
        """Notification updated well within the retention window is excluded."""
        recent = datetime.now(tz=UTC) - timedelta(days=89)
        make_db_notification(db, status="expired", updated_at=recent)
        result = get_retention_candidates(db)
        assert len(result) == 0

    def test_boundary_past_side_included(self, db):
        """Notification updated well past the retention window is included."""
        old = datetime.now(tz=UTC) - timedelta(days=91)
        make_db_notification(db, status="expired", updated_at=old)
        result = get_retention_candidates(db)
        assert len(result) == 1


# ===========================================================================
# Integration tests — PATCH delivery auto-populates expires_at
# ===========================================================================


class TestDeliveryExpiryIntegration:
    """PATCH to delivered status auto-populates expires_at."""

    @pytest.mark.parametrize("ntype", [
        t for t in NOTIFICATION_TYPES if t != "deadline_event_alert"
    ])
    def test_auto_populates_on_delivery(self, client, ntype):
        notif = make_notification(client, notification_type=ntype)
        assert notif["expires_at"] is None

        delivered = deliver(client, notif["id"])
        assert delivered["expires_at"] is not None

    def test_deadline_event_alert_gets_24h_fallback(self, client):
        notif = make_notification(
            client, notification_type="deadline_event_alert",
        )
        before = datetime.now(tz=UTC)
        delivered = deliver(client, notif["id"])
        expires = datetime.fromisoformat(delivered["expires_at"]).replace(tzinfo=UTC)
        # Should be ~24h from delivery time
        delta = expires - before
        assert timedelta(hours=23, minutes=59) < delta < timedelta(hours=24, seconds=5)

    def test_explicit_expires_at_preserved_on_delivery(self, client):
        override_str = "2026-04-20T17:00:00Z"
        notif = make_notification(client, expires_at=override_str)
        delivered = deliver(client, notif["id"])
        expires = datetime.fromisoformat(delivered["expires_at"]).replace(tzinfo=UTC)
        assert expires == datetime(2026, 4, 20, 17, 0, tzinfo=UTC)

    def test_explicit_expires_at_preserved_for_deadline(self, client):
        override_str = "2026-04-16T23:59:00Z"
        notif = make_notification(
            client,
            notification_type="deadline_event_alert",
            expires_at=override_str,
        )
        delivered = deliver(client, notif["id"])
        expires = datetime.fromisoformat(delivered["expires_at"]).replace(tzinfo=UTC)
        assert expires == datetime(2026, 4, 16, 23, 59, tzinfo=UTC)

    def test_habit_nudge_expires_approx_4h(self, client):
        notif = make_notification(client, notification_type="habit_nudge")
        before = datetime.now(tz=UTC)
        delivered = deliver(client, notif["id"])
        expires = datetime.fromisoformat(delivered["expires_at"]).replace(tzinfo=UTC)
        delta = expires - before
        assert timedelta(hours=3, minutes=59) < delta < timedelta(hours=4, seconds=5)

    def test_expires_at_not_set_on_patch_without_delivery(self, client):
        """PATCH that doesn't transition to delivered doesn't touch expires_at."""
        notif = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{notif['id']}",
            json={"message": "Updated message"},
        )
        assert resp.status_code == 200
        assert resp.json()["expires_at"] is None
