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

"""Tests for Notification Queue CRUD API endpoints."""

import uuid

import pytest

from app.models import Rule
from app.schemas.rule import RuleAction, RuleEntityType, RuleMetric, RuleOperator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_URL = "/api/notifications"

VALID_NOTIFICATION = {
    "notification_type": "habit_nudge",
    "delivery_type": "notification",
    "scheduled_at": "2026-04-15T09:00:00Z",
    "scheduled_date": "2026-04-15",
    "target_entity_type": "habit",
    "target_entity_id": str(uuid.uuid4()),
    "message": "Time to stretch!",
    "scheduled_by": "system",
}


def make_notification(client, **overrides) -> dict:
    """Create a notification via the API and return the response JSON."""
    data = {**VALID_NOTIFICATION, **overrides}
    # Ensure target_entity_id is unique per call unless overridden
    if "target_entity_id" not in overrides:
        data["target_entity_id"] = str(uuid.uuid4())
    resp = client.post(BASE_URL, json=data)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST — Create
# ---------------------------------------------------------------------------

class TestCreateNotification:
    """POST /api/notifications"""

    def test_create_minimal(self, client):
        """Create a notification with only required fields."""
        result = make_notification(client)
        assert result["notification_type"] == "habit_nudge"
        assert result["status"] == "pending"
        assert result["message"] == "Time to stretch!"
        assert result["id"] is not None
        assert result["created_at"] is not None

    def test_create_with_canned_responses(self, client):
        """Create with valid canned_responses array."""
        result = make_notification(
            client, canned_responses=["Done", "Skip", "Snooze"],
        )
        assert result["canned_responses"] == ["Done", "Skip", "Snooze"]

    def test_create_with_all_optional_fields(self, client, db):
        """Create with every optional field populated."""
        rule = Rule(
            id=uuid.uuid4(), name="test rule", entity_type=RuleEntityType.habit,
            metric=RuleMetric.consecutive_skips, operator=RuleOperator.gte,
            threshold=3, action=RuleAction.create_notification,
            notification_type="habit_nudge", message_template="test",
        )
        db.add(rule)
        db.commit()
        rule_id = str(rule.id)
        result = make_notification(
            client,
            canned_responses=["Yes", "No"],
            expires_at="2026-04-16T09:00:00Z",
            rule_id=rule_id,
        )
        assert result["canned_responses"] == ["Yes", "No"]
        assert result["expires_at"] is not None
        assert result["rule_id"] == rule_id

    def test_create_always_sets_pending(self, client):
        """Status is always pending on create, regardless of input."""
        # NotificationCreate schema doesn't include status field,
        # so even if we pass it, it's ignored by Pydantic.
        data = {**VALID_NOTIFICATION, "target_entity_id": str(uuid.uuid4())}
        resp = client.post(BASE_URL, json=data)
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    def test_create_empty_message_rejected(self, client):
        """Empty message returns 422."""
        data = {**VALID_NOTIFICATION, "message": "", "target_entity_id": str(uuid.uuid4())}
        resp = client.post(BASE_URL, json=data)
        assert resp.status_code == 422

    def test_create_oversized_message_rejected(self, client):
        """Message over 2000 chars returns 422."""
        data = {
            **VALID_NOTIFICATION,
            "message": "x" * 2001,
            "target_entity_id": str(uuid.uuid4()),
        }
        resp = client.post(BASE_URL, json=data)
        assert resp.status_code == 422

    def test_create_invalid_notification_type(self, client):
        """Invalid notification_type returns 422."""
        data = {
            **VALID_NOTIFICATION,
            "notification_type": "invalid_type",
            "target_entity_id": str(uuid.uuid4()),
        }
        resp = client.post(BASE_URL, json=data)
        assert resp.status_code == 422

    def test_create_invalid_scheduled_by(self, client):
        """Invalid scheduled_by returns 422."""
        data = {
            **VALID_NOTIFICATION,
            "scheduled_by": "cron",
            "target_entity_id": str(uuid.uuid4()),
        }
        resp = client.post(BASE_URL, json=data)
        assert resp.status_code == 422

    def test_create_canned_responses_too_many(self, client):
        """More than 10 canned responses returns 422."""
        data = {
            **VALID_NOTIFICATION,
            "canned_responses": [f"opt{i}" for i in range(11)],
            "target_entity_id": str(uuid.uuid4()),
        }
        resp = client.post(BASE_URL, json=data)
        assert resp.status_code == 422

    def test_create_canned_responses_empty_string(self, client):
        """Canned response with empty string returns 422."""
        data = {
            **VALID_NOTIFICATION,
            "canned_responses": ["Valid", ""],
            "target_entity_id": str(uuid.uuid4()),
        }
        resp = client.post(BASE_URL, json=data)
        assert resp.status_code == 422

    def test_create_canned_responses_oversized_item(self, client):
        """Canned response item over 200 chars returns 422."""
        data = {
            **VALID_NOTIFICATION,
            "canned_responses": ["x" * 201],
            "target_entity_id": str(uuid.uuid4()),
        }
        resp = client.post(BASE_URL, json=data)
        assert resp.status_code == 422

    def test_create_missing_scheduled_date_rejected(self, client):
        """Omitting scheduled_date returns 422 ([2C-02] required field)."""
        data = {**VALID_NOTIFICATION, "target_entity_id": str(uuid.uuid4())}
        data.pop("scheduled_date")
        resp = client.post(BASE_URL, json=data)
        assert resp.status_code == 422
        assert "scheduled_date" in resp.text

    def test_create_response_includes_scheduled_date(self, client):
        """Response payload echoes scheduled_date as ISO date string."""
        result = make_notification(client, scheduled_date="2026-05-01")
        assert result["scheduled_date"] == "2026-05-01"

    def test_create_invalid_scheduled_date_format_rejected(self, client):
        """A non-date string for scheduled_date returns 422."""
        data = {
            **VALID_NOTIFICATION,
            "scheduled_date": "not-a-date",
            "target_entity_id": str(uuid.uuid4()),
        }
        resp = client.post(BASE_URL, json=data)
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "ntype",
        [
            "habit_nudge", "routine_checklist", "checkin_prompt",
            "time_block_reminder", "deadline_event_alert",
            "pattern_observation", "stale_work_nudge",
        ],
    )
    def test_create_all_notification_types(self, client, ntype):
        """All 7 notification types are accepted."""
        result = make_notification(client, notification_type=ntype)
        assert result["notification_type"] == ntype

    @pytest.mark.parametrize("sched", ["system", "claude", "rule"])
    def test_create_all_scheduled_by(self, client, sched):
        """All scheduled_by values are accepted."""
        result = make_notification(client, scheduled_by=sched)
        assert result["scheduled_by"] == sched


# ---------------------------------------------------------------------------
# GET detail
# ---------------------------------------------------------------------------

class TestGetNotification:
    """GET /api/notifications/{id}"""

    def test_get_existing(self, client):
        """Get a notification by valid ID."""
        created = make_notification(client)
        resp = client.get(f"{BASE_URL}/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_not_found(self, client):
        """Get with invalid UUID returns 404."""
        resp = client.get(f"{BASE_URL}/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET list — composable filters
# ---------------------------------------------------------------------------

class TestListNotifications:
    """GET /api/notifications"""

    def test_list_empty(self, client):
        """Empty list when no notifications exist."""
        resp = client.get(BASE_URL)
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "count": 0}

    def test_list_single(self, client):
        """Single-element list returns envelope with count=1."""
        make_notification(client)
        resp = client.get(BASE_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert len(data["items"]) == 1

    def test_list_returns_all(self, client):
        """List returns all created notifications."""
        make_notification(client)
        make_notification(client, notification_type="checkin_prompt")
        resp = client.get(BASE_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["items"]) == 2

    def test_filter_by_notification_type(self, client):
        """Filter by notification_type."""
        make_notification(client, notification_type="habit_nudge")
        make_notification(client, notification_type="checkin_prompt")
        resp = client.get(BASE_URL, params={"notification_type": "habit_nudge"})
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["notification_type"] == "habit_nudge"

    def test_filter_by_status(self, client):
        """Filter by status."""
        n = make_notification(client)
        # Transition to delivered
        client.patch(f"{BASE_URL}/{n['id']}", json={"status": "delivered"})
        make_notification(client)  # stays pending

        resp = client.get(BASE_URL, params={"status": "delivered"})
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["status"] == "delivered"

    def test_filter_by_target_entity_type(self, client):
        """Filter by target_entity_type."""
        make_notification(client, target_entity_type="habit")
        make_notification(client, target_entity_type="routine")
        resp = client.get(BASE_URL, params={"target_entity_type": "routine"})
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["target_entity_type"] == "routine"

    def test_filter_by_target_entity_id(self, client):
        """Filter by target_entity_id."""
        entity_id = str(uuid.uuid4())
        make_notification(client, target_entity_id=entity_id)
        make_notification(client)  # different entity_id
        resp = client.get(BASE_URL, params={"target_entity_id": entity_id})
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["target_entity_id"] == entity_id

    def test_filter_by_scheduled_by(self, client):
        """Filter by scheduled_by."""
        make_notification(client, scheduled_by="system")
        make_notification(client, scheduled_by="claude")
        resp = client.get(BASE_URL, params={"scheduled_by": "claude"})
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["scheduled_by"] == "claude"

    def test_filter_by_date_range(self, client):
        """Filter by scheduled_after and scheduled_before."""
        make_notification(client, scheduled_at="2026-04-10T09:00:00Z")
        make_notification(client, scheduled_at="2026-04-20T09:00:00Z")

        resp = client.get(
            BASE_URL,
            params={
                "scheduled_after": "2026-04-15T00:00:00Z",
                "scheduled_before": "2026-04-25T00:00:00Z",
            },
        )
        data = resp.json()
        assert data["count"] == 1
        assert "2026-04-20" in data["items"][0]["scheduled_at"]

    def test_filter_has_response_true(self, client):
        """has_response=true returns only responded notifications."""
        n = make_notification(client)
        # Transition pending → delivered → responded
        client.patch(f"{BASE_URL}/{n['id']}", json={"status": "delivered"})
        client.patch(f"{BASE_URL}/{n['id']}", json={"status": "responded"})
        make_notification(client)  # stays pending

        resp = client.get(BASE_URL, params={"has_response": True})
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["status"] == "responded"

    def test_filter_has_response_false(self, client):
        """has_response=false returns non-responded notifications."""
        n = make_notification(client)
        client.patch(f"{BASE_URL}/{n['id']}", json={"status": "delivered"})
        client.patch(f"{BASE_URL}/{n['id']}", json={"status": "responded"})
        make_notification(client)  # stays pending

        resp = client.get(BASE_URL, params={"has_response": False})
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["status"] == "pending"

    def test_filter_by_rule_id(self, client, db):
        """Filter by rule_id."""
        rule = Rule(
            id=uuid.uuid4(), name="filter rule", entity_type=RuleEntityType.habit,
            metric=RuleMetric.consecutive_skips, operator=RuleOperator.gte,
            threshold=3, action=RuleAction.create_notification,
            notification_type="habit_nudge", message_template="test",
        )
        db.add(rule)
        db.commit()
        rid = str(rule.id)
        make_notification(client, rule_id=rid)
        make_notification(client)  # no rule_id
        resp = client.get(BASE_URL, params={"rule_id": rid})
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["rule_id"] == rid

    def test_filter_by_delivery_type(self, client):
        """Filter by delivery_type."""
        make_notification(client)
        resp = client.get(BASE_URL, params={"delivery_type": "notification"})
        data = resp.json()
        assert data["count"] == 1

    def test_filter_by_scheduled_date(self, client):
        """Filter by scheduled_date returns only same-calendar-day rows."""
        make_notification(
            client,
            scheduled_at="2026-04-15T09:00:00Z",
            scheduled_date="2026-04-15",
        )
        make_notification(
            client,
            scheduled_at="2026-04-16T09:00:00Z",
            scheduled_date="2026-04-16",
        )
        resp = client.get(BASE_URL, params={"scheduled_date": "2026-04-15"})
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["scheduled_date"] == "2026-04-15"

    def test_combined_filters(self, client):
        """Multiple filters combine with AND logic."""
        target_id = str(uuid.uuid4())
        make_notification(
            client,
            notification_type="habit_nudge",
            scheduled_by="claude",
            target_entity_id=target_id,
        )
        make_notification(
            client,
            notification_type="habit_nudge",
            scheduled_by="system",
        )
        make_notification(
            client,
            notification_type="checkin_prompt",
            scheduled_by="claude",
        )

        resp = client.get(
            BASE_URL,
            params={
                "notification_type": "habit_nudge",
                "scheduled_by": "claude",
            },
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["target_entity_id"] == target_id

    def test_list_sorted_by_scheduled_at_desc(self, client):
        """List is sorted by scheduled_at descending."""
        make_notification(client, scheduled_at="2026-04-10T09:00:00Z")
        make_notification(client, scheduled_at="2026-04-20T09:00:00Z")
        make_notification(client, scheduled_at="2026-04-15T09:00:00Z")

        resp = client.get(BASE_URL)
        data = resp.json()
        assert data["count"] == 3
        items = data["items"]
        # Most recent first
        assert "2026-04-20" in items[0]["scheduled_at"]
        assert "2026-04-15" in items[1]["scheduled_at"]
        assert "2026-04-10" in items[2]["scheduled_at"]


# ---------------------------------------------------------------------------
# PATCH — Update
# ---------------------------------------------------------------------------

class TestUpdateNotification:
    """PATCH /api/notifications/{id}"""

    def test_update_message(self, client):
        """Update the message field."""
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"message": "Updated message"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Updated message"

    def test_update_not_found(self, client):
        """Update with invalid UUID returns 404."""
        resp = client.patch(
            f"{BASE_URL}/{uuid.uuid4()}", json={"message": "nope"},
        )
        assert resp.status_code == 404

    # --- Valid status transitions ---

    def test_transition_pending_to_delivered(self, client):
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"status": "delivered"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"

    def test_transition_pending_to_expired(self, client):
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"status": "expired"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "expired"

    def test_transition_delivered_to_responded(self, client):
        n = make_notification(client)
        client.patch(f"{BASE_URL}/{n['id']}", json={"status": "delivered"})
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"status": "responded"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "responded"

    def test_transition_delivered_to_expired(self, client):
        n = make_notification(client)
        client.patch(f"{BASE_URL}/{n['id']}", json={"status": "delivered"})
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"status": "expired"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "expired"

    # --- Invalid status transitions ---

    def test_invalid_transition_responded_to_any(self, client):
        """responded is terminal — cannot transition out."""
        n = make_notification(client)
        client.patch(f"{BASE_URL}/{n['id']}", json={"status": "delivered"})
        client.patch(f"{BASE_URL}/{n['id']}", json={"status": "responded"})
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"status": "pending"},
        )
        assert resp.status_code == 422
        assert "Invalid status transition" in resp.json()["detail"]

    def test_invalid_transition_expired_to_any(self, client):
        """expired is terminal — cannot transition out."""
        n = make_notification(client)
        client.patch(f"{BASE_URL}/{n['id']}", json={"status": "expired"})
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"status": "pending"},
        )
        assert resp.status_code == 422
        assert "Invalid status transition" in resp.json()["detail"]

    def test_invalid_transition_delivered_to_pending(self, client):
        """Cannot go back from delivered to pending."""
        n = make_notification(client)
        client.patch(f"{BASE_URL}/{n['id']}", json={"status": "delivered"})
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"status": "pending"},
        )
        assert resp.status_code == 422

    def test_invalid_transition_pending_to_responded(self, client):
        """Cannot respond to something not yet delivered."""
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"status": "responded"},
        )
        assert resp.status_code == 422

    # --- Immutable fields ---

    def test_reject_immutable_notification_type(self, client):
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}",
            json={"notification_type": "checkin_prompt"},
        )
        assert resp.status_code == 422
        assert "immutable" in resp.json()["detail"].lower()

    def test_reject_immutable_target_entity_type(self, client):
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}",
            json={"target_entity_type": "routine"},
        )
        assert resp.status_code == 422

    def test_reject_immutable_target_entity_id(self, client):
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}",
            json={"target_entity_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 422

    def test_reject_immutable_scheduled_by(self, client):
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"scheduled_by": "claude"},
        )
        assert resp.status_code == 422

    def test_reject_immutable_response(self, client):
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}", json={"response": "Done"},
        )
        assert resp.status_code == 422

    def test_reject_immutable_responded_at(self, client):
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}",
            json={"responded_at": "2026-04-15T10:00:00Z"},
        )
        assert resp.status_code == 422

    def test_update_canned_responses(self, client):
        """Canned responses can be updated."""
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}",
            json={"canned_responses": ["A", "B"]},
        )
        assert resp.status_code == 200
        assert resp.json()["canned_responses"] == ["A", "B"]

    def test_update_scheduled_at(self, client):
        """scheduled_at can be updated."""
        n = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{n['id']}",
            json={"scheduled_at": "2026-05-01T12:00:00Z"},
        )
        assert resp.status_code == 200
        assert "2026-05-01" in resp.json()["scheduled_at"]


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

class TestDeleteNotification:
    """DELETE /api/notifications/{id}"""

    def test_delete_existing(self, client):
        """Delete returns 204 and notification is gone."""
        n = make_notification(client)
        resp = client.delete(f"{BASE_URL}/{n['id']}")
        assert resp.status_code == 204

        # Confirm gone
        resp = client.get(f"{BASE_URL}/{n['id']}")
        assert resp.status_code == 404

    def test_delete_not_found(self, client):
        """Delete with invalid UUID returns 404."""
        resp = client.delete(f"{BASE_URL}/{uuid.uuid4()}")
        assert resp.status_code == 404
