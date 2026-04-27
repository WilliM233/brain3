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

"""Tests for [2B-04] canned response defaults and validation."""

import uuid

import pytest

from app.services.notification_defaults import (
    CANNED_RESPONSE_DEFAULTS,
    get_default_responses,
    validate_canned_responses,
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


# ===========================================================================
# Unit tests — CANNED_RESPONSE_DEFAULTS constant
# ===========================================================================


class TestCannedResponseDefaults:
    """The defaults dict covers all 7 notification types."""

    def test_all_types_present(self):
        for ntype in NOTIFICATION_TYPES:
            assert ntype in CANNED_RESPONSE_DEFAULTS

    def test_no_extra_types(self):
        assert set(CANNED_RESPONSE_DEFAULTS.keys()) == set(NOTIFICATION_TYPES)

    @pytest.mark.parametrize("ntype", NOTIFICATION_TYPES)
    def test_defaults_are_non_empty_string_lists(self, ntype):
        defaults = CANNED_RESPONSE_DEFAULTS[ntype]
        assert isinstance(defaults, list)
        assert len(defaults) >= 1
        for item in defaults:
            assert isinstance(item, str)
            assert len(item) >= 1


# ===========================================================================
# Unit tests — get_default_responses
# ===========================================================================


class TestGetDefaultResponses:
    """get_default_responses returns a copy of defaults, or None."""

    @pytest.mark.parametrize("ntype", NOTIFICATION_TYPES)
    def test_returns_defaults_for_known_types(self, ntype):
        result = get_default_responses(ntype)
        assert result == CANNED_RESPONSE_DEFAULTS[ntype]

    def test_returns_none_for_unknown_type(self):
        assert get_default_responses("nonexistent_type") is None

    def test_returns_copy_not_reference(self):
        result = get_default_responses("habit_nudge")
        result.append("mutated")
        assert "mutated" not in CANNED_RESPONSE_DEFAULTS["habit_nudge"]


# ===========================================================================
# Unit tests — validate_canned_responses
# ===========================================================================


class TestValidateCannedResponses:
    """Validation rules from the spec."""

    def test_valid_single_item(self):
        validate_canned_responses(["OK"])

    def test_valid_ten_items(self):
        validate_canned_responses([f"Option {i}" for i in range(10)])

    def test_valid_200_char_string(self):
        validate_canned_responses(["x" * 200])

    def test_rejects_empty_list(self):
        with pytest.raises(ValueError, match="at least 1 option"):
            validate_canned_responses([])

    def test_rejects_more_than_10(self):
        with pytest.raises(ValueError, match="cannot exceed 10"):
            validate_canned_responses([f"Option {i}" for i in range(11)])

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError, match="cannot be blank"):
            validate_canned_responses([""])

    def test_rejects_whitespace_only_string(self):
        with pytest.raises(ValueError, match="cannot be blank"):
            validate_canned_responses(["   "])

    def test_rejects_string_over_200_chars(self):
        with pytest.raises(ValueError, match="1-200 characters"):
            validate_canned_responses(["x" * 201])

    def test_rejects_duplicates(self):
        with pytest.raises(ValueError, match="duplicate entries"):
            validate_canned_responses(["Same", "Same"])

    def test_rejects_non_string_item(self):
        with pytest.raises(ValueError, match="array of strings"):
            validate_canned_responses([123])  # type: ignore[list-item]

    def test_rejects_non_list(self):
        with pytest.raises(ValueError, match="array of strings"):
            validate_canned_responses("not a list")  # type: ignore[arg-type]


# ===========================================================================
# Integration tests — auto-population on create
# ===========================================================================


class TestAutoPopulationOnCreate:
    """When canned_responses is omitted, defaults are auto-populated."""

    @pytest.mark.parametrize("ntype", NOTIFICATION_TYPES)
    def test_auto_populates_defaults_when_omitted(self, client, ntype):
        notif = make_notification(client, notification_type=ntype)
        assert notif["canned_responses"] == CANNED_RESPONSE_DEFAULTS[ntype]

    @pytest.mark.parametrize("ntype", NOTIFICATION_TYPES)
    def test_auto_populates_defaults_when_null(self, client, ntype):
        notif = make_notification(
            client, notification_type=ntype, canned_responses=None,
        )
        assert notif["canned_responses"] == CANNED_RESPONSE_DEFAULTS[ntype]

    def test_explicit_canned_responses_preserved(self, client):
        custom = ["Yes", "No", "Maybe"]
        notif = make_notification(client, canned_responses=custom)
        assert notif["canned_responses"] == custom

    def test_explicit_single_item_preserved(self, client):
        custom = ["Acknowledged"]
        notif = make_notification(client, canned_responses=custom)
        assert notif["canned_responses"] == custom


# ===========================================================================
# Integration tests — validation through the API
# ===========================================================================


class TestValidationThroughAPI:
    """Validation errors return 422 through create and update endpoints."""

    def test_create_rejects_empty_list(self, client):
        resp = client.post(BASE_URL, json={
            "notification_type": "habit_nudge",
            "scheduled_at": "2026-04-15T09:00:00Z",
            "target_entity_type": "habit",
            "target_entity_id": str(uuid.uuid4()),
            "message": "Test",
            "scheduled_by": "system",
            "canned_responses": [],
        })
        assert resp.status_code == 422

    def test_create_rejects_more_than_10(self, client):
        resp = client.post(BASE_URL, json={
            "notification_type": "habit_nudge",
            "scheduled_at": "2026-04-15T09:00:00Z",
            "target_entity_type": "habit",
            "target_entity_id": str(uuid.uuid4()),
            "message": "Test",
            "scheduled_by": "system",
            "canned_responses": [f"Opt {i}" for i in range(11)],
        })
        assert resp.status_code == 422

    def test_create_rejects_blank_string(self, client):
        resp = client.post(BASE_URL, json={
            "notification_type": "habit_nudge",
            "scheduled_at": "2026-04-15T09:00:00Z",
            "target_entity_type": "habit",
            "target_entity_id": str(uuid.uuid4()),
            "message": "Test",
            "scheduled_by": "system",
            "canned_responses": ["   "],
        })
        assert resp.status_code == 422

    def test_create_rejects_string_over_200(self, client):
        resp = client.post(BASE_URL, json={
            "notification_type": "habit_nudge",
            "scheduled_at": "2026-04-15T09:00:00Z",
            "target_entity_type": "habit",
            "target_entity_id": str(uuid.uuid4()),
            "message": "Test",
            "scheduled_by": "system",
            "canned_responses": ["x" * 201],
        })
        assert resp.status_code == 422

    def test_create_rejects_duplicates(self, client):
        resp = client.post(BASE_URL, json={
            "notification_type": "habit_nudge",
            "scheduled_at": "2026-04-15T09:00:00Z",
            "target_entity_type": "habit",
            "target_entity_id": str(uuid.uuid4()),
            "message": "Test",
            "scheduled_by": "system",
            "canned_responses": ["Same", "Same"],
        })
        assert resp.status_code == 422

    def test_update_rejects_empty_list(self, client):
        notif = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{notif['id']}", json={"canned_responses": []},
        )
        assert resp.status_code == 422

    def test_update_rejects_duplicates(self, client):
        notif = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{notif['id']}",
            json={"canned_responses": ["Dup", "Dup"]},
        )
        assert resp.status_code == 422

    def test_update_accepts_valid_canned_responses(self, client):
        notif = make_notification(client)
        resp = client.patch(
            f"{BASE_URL}/{notif['id']}",
            json={"canned_responses": ["New A", "New B"]},
        )
        assert resp.status_code == 200
        assert resp.json()["canned_responses"] == ["New A", "New B"]
