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

"""Tests for POST /api/notifications/{id}/respond endpoint."""

import uuid

import pytest

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

# Canned responses per notification type (representative examples from the design doc)
TYPE_CANNED_RESPONSES = {
    "habit_nudge": ["Already done", "Doing it now", "I forgot, on it", "Skip today"],
    "routine_checklist": ["All done", "Partial", "Skipping tonight"],
    "checkin_prompt": ["Feeling good", "Okay", "Struggling"],
    "time_block_reminder": ["On it", "Need more time", "Skipping"],
    "deadline_event_alert": ["Acknowledged", "Need help"],
    "pattern_observation": ["Thanks", "Noted"],
    "stale_work_nudge": ["On it", "Deprioritized", "Done already"],
}


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
    if "target_entity_id" not in overrides:
        data["target_entity_id"] = str(uuid.uuid4())
    resp = client.post(BASE_URL, json=data)
    assert resp.status_code == 201, resp.text
    return resp.json()


def deliver(client, notification_id: str) -> dict:
    """Transition a notification from pending → delivered."""
    resp = client.patch(
        f"{BASE_URL}/{notification_id}", json={"status": "delivered"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def expire(client, notification_id: str) -> dict:
    """Transition a notification to expired (pending → expired)."""
    resp = client.patch(
        f"{BASE_URL}/{notification_id}", json={"status": "expired"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Happy path — response for each notification type
# ---------------------------------------------------------------------------

class TestRespondHappyPath:
    """POST /api/notifications/{id}/respond — success cases."""

    @pytest.mark.parametrize("ntype", NOTIFICATION_TYPES)
    def test_respond_each_notification_type(self, client, ntype):
        """Response accepted for each of the 7 notification types."""
        canned = TYPE_CANNED_RESPONSES[ntype]
        n = make_notification(
            client,
            notification_type=ntype,
            canned_responses=canned,
        )
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": canned[0]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "responded"
        assert body["response"] == canned[0]
        assert body["responded_at"] is not None

    def test_respond_sets_responded_at_utc(self, client):
        """responded_at is set to a UTC timestamp on success."""
        n = make_notification(
            client, canned_responses=["Done"],
        )
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "Done"},
        )
        assert resp.status_code == 200
        assert resp.json()["responded_at"] is not None

    def test_respond_with_response_note(self, client):
        """response_note is stored when provided."""
        n = make_notification(
            client, canned_responses=["Done", "Skip"],
        )
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "Done", "response_note": "Did it early today"},
        )
        assert resp.status_code == 200
        assert resp.json()["response_note"] == "Did it early today"


# ---------------------------------------------------------------------------
# Partial completion
# ---------------------------------------------------------------------------

class TestPartialCompletion:
    """Partial response is always valid regardless of canned_responses."""

    def test_partial_accepted_with_canned_responses(self, client):
        """'partial' accepted even when not in canned_responses list."""
        n = make_notification(
            client,
            canned_responses=["All done", "Skipping tonight"],
        )
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "partial"},
        )
        assert resp.status_code == 200
        assert resp.json()["response"] == "partial"
        assert resp.json()["status"] == "responded"

    def test_partial_with_response_note(self, client):
        """'partial' with freeform response_note."""
        n = make_notification(
            client, canned_responses=["Done"],
        )
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "partial", "response_note": "Did 3 of 5 items"},
        )
        assert resp.status_code == 200
        assert resp.json()["response"] == "partial"
        assert resp.json()["response_note"] == "Did 3 of 5 items"

    def test_partial_without_response_note(self, client):
        """'partial' without response_note is valid."""
        n = make_notification(
            client, canned_responses=["Done"],
        )
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "partial"},
        )
        assert resp.status_code == 200
        assert resp.json()["response_note"] is None


# ---------------------------------------------------------------------------
# Null canned_responses — any non-empty response accepted
# ---------------------------------------------------------------------------

class TestNullCannedResponses:
    """Notifications with null canned_responses accept any non-empty response."""

    def test_any_response_accepted_when_canned_responses_cleared(self, client):
        """Any string accepted when canned_responses is explicitly cleared to null."""
        n = make_notification(client)
        # Auto-populated defaults are present; clear them via PATCH
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"canned_responses": None},
        )
        assert resp.status_code == 200
        assert resp.json()["canned_responses"] is None
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "Freestyle answer"},
        )
        assert resp.status_code == 200
        assert resp.json()["response"] == "Freestyle answer"

    def test_defaults_auto_populated_when_omitted(self, client):
        """Omitting canned_responses auto-populates from type defaults."""
        n = make_notification(client)  # habit_nudge, no explicit canned_responses
        assert n["canned_responses"] is not None
        assert "Already done" in n["canned_responses"]

    def test_partial_also_accepted(self, client):
        """'partial' still works with null canned_responses."""
        n = make_notification(client)
        # Clear auto-populated defaults
        client.patch(f"{BASE_URL}/{n['id']}", json={"canned_responses": None})
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "partial"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestRespondErrors:
    """POST /api/notifications/{id}/respond — error scenarios."""

    def test_404_not_found(self, client):
        """Invalid notification ID returns 404."""
        resp = client.post(
            f"{BASE_URL}/{uuid.uuid4()}/respond",
            json={"response": "Done"},
        )
        assert resp.status_code == 404

    def test_409_pending_not_delivered(self, client):
        """Responding to a pending notification returns 409."""
        n = make_notification(client, canned_responses=["Done"])
        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "Done"},
        )
        assert resp.status_code == 409
        assert "not been delivered" in resp.json()["detail"]

    def test_409_already_responded(self, client):
        """Responding to an already-responded notification returns 409."""
        n = make_notification(client, canned_responses=["Done"])
        deliver(client, n["id"])
        # First response
        client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "Done"},
        )
        # Second response attempt
        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "Done"},
        )
        assert resp.status_code == 409
        assert "already been responded to" in resp.json()["detail"]

    def test_410_expired(self, client):
        """Responding to an expired notification returns 410."""
        n = make_notification(client, canned_responses=["Done"])
        expire(client, n["id"])
        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "Done"},
        )
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"]

    def test_422_invalid_response(self, client):
        """Response not in canned_responses (and not 'partial') returns 422."""
        n = make_notification(
            client, canned_responses=["Done", "Skip"],
        )
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "Not a valid option"},
        )
        assert resp.status_code == 422

    def test_422_empty_response(self, client):
        """Empty string response returns 422 (Pydantic min_length=1)."""
        n = make_notification(client, canned_responses=["Done"])
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": ""},
        )
        assert resp.status_code == 422

    def test_422_response_too_long(self, client):
        """Response over 200 chars returns 422."""
        n = make_notification(client)
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "x" * 201},
        )
        assert resp.status_code == 422

    def test_422_response_note_too_long(self, client):
        """response_note over 1000 chars returns 422."""
        n = make_notification(client, canned_responses=["Done"])
        deliver(client, n["id"])

        resp = client.post(
            f"{BASE_URL}/{n['id']}/respond",
            json={"response": "Done", "response_note": "x" * 1001},
        )
        assert resp.status_code == 422
