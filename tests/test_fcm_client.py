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

"""Tests for the FCM client surface (``app/services/fcm.py``).

Covers configuration gating and the FCM error-body → :class:`FcmResult`
classifier — the two pieces of pure logic the dispatch path relies on.
The actual HTTPS round-trip is mocked in ``test_delivery_dispatch.py``.
"""

from __future__ import annotations

from app.services import fcm
from app.services.fcm import FcmStatus, _classify_error, send_notification_to_device


class TestIsConfigured:
    """Both env values must be set for FCM dispatch to be attempted."""

    def test_returns_false_when_project_id_missing(self, monkeypatch) -> None:
        monkeypatch.setattr(fcm.settings, "FCM_PROJECT_ID", None)
        monkeypatch.setattr(
            fcm.settings, "FCM_SERVICE_ACCOUNT_JSON_PATH", "/path/to/sa.json",
        )
        assert fcm.is_configured() is False

    def test_returns_false_when_service_account_missing(self, monkeypatch) -> None:
        monkeypatch.setattr(fcm.settings, "FCM_PROJECT_ID", "demo-project")
        monkeypatch.setattr(fcm.settings, "FCM_SERVICE_ACCOUNT_JSON_PATH", None)
        assert fcm.is_configured() is False

    def test_returns_true_when_both_set(self, monkeypatch) -> None:
        monkeypatch.setattr(fcm.settings, "FCM_PROJECT_ID", "demo-project")
        monkeypatch.setattr(
            fcm.settings, "FCM_SERVICE_ACCOUNT_JSON_PATH", "/run/secrets/sa.json",
        )
        assert fcm.is_configured() is True


class TestSendWhenNotConfigured:
    """Calling send when FCM is unconfigured returns NOT_CONFIGURED, not raise."""

    def test_returns_not_configured(self, monkeypatch) -> None:
        monkeypatch.setattr(fcm.settings, "FCM_PROJECT_ID", None)
        monkeypatch.setattr(fcm.settings, "FCM_SERVICE_ACCOUNT_JSON_PATH", None)

        result = send_notification_to_device("any-token", {"data": {}})

        assert result.status == FcmStatus.NOT_CONFIGURED
        assert result.token_invalidated is False


class TestClassifyError:
    """``_classify_error`` maps FCM v1 error envelopes onto status enums."""

    def test_unregistered_via_error_code(self) -> None:
        body = {
            "error": {
                "code": 404,
                "status": "NOT_FOUND",
                "message": "Requested entity was not found.",
                "details": [{"errorCode": "UNREGISTERED"}],
            },
        }
        result = _classify_error(404, body)
        assert result.status == FcmStatus.UNREGISTERED
        assert result.token_invalidated is True
        assert result.error_code == "UNREGISTERED"

    def test_invalid_argument_via_error_code(self) -> None:
        body = {
            "error": {
                "code": 400,
                "status": "INVALID_ARGUMENT",
                "message": "The registration token is not a valid FCM token.",
                "details": [{"errorCode": "INVALID_ARGUMENT"}],
            },
        }
        result = _classify_error(400, body)
        assert result.status == FcmStatus.INVALID_ARGUMENT
        assert result.token_invalidated is True

    def test_unauthenticated_classified_as_auth_failed(self) -> None:
        body = {"error": {"status": "UNAUTHENTICATED", "message": "bad token"}}
        result = _classify_error(401, body)
        assert result.status == FcmStatus.AUTH_FAILED
        assert result.token_invalidated is False

    def test_rate_limited(self) -> None:
        body = {"error": {"status": "RESOURCE_EXHAUSTED", "message": "too many"}}
        result = _classify_error(429, body)
        assert result.status == FcmStatus.RATE_LIMITED
        assert result.token_invalidated is False

    def test_server_error_default(self) -> None:
        body = {"error": {"status": "INTERNAL", "message": "boom"}}
        result = _classify_error(500, body)
        assert result.status == FcmStatus.SERVER_ERROR
        assert result.token_invalidated is False

    def test_404_without_explicit_error_code_still_unregistered(self) -> None:
        """Defensive: a 404 without details still flags the token as dead."""
        result = _classify_error(404, {})
        assert result.status == FcmStatus.UNREGISTERED

    def test_400_without_explicit_error_code_still_invalid(self) -> None:
        result = _classify_error(400, {})
        assert result.status == FcmStatus.INVALID_ARGUMENT
