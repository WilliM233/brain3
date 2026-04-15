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

"""Tests for [2F-04] Default Rules — Seed Data.

Verifies the four default rules, is_default column behavior,
idempotent seeding, and API filter support.
"""

import json
from pathlib import Path

import pytest

from app.models import Rule
from app.schemas.rule import (
    RuleAction,
    RuleCreate,
    RuleEntityType,
    RuleMetric,
    RuleOperator,
    validate_message_template,
)

RULES_URL = "/api/rules"
SEEDS_DIR = Path(__file__).parent.parent / "scripts" / "seeds"

# ---------------------------------------------------------------------------
# Seed data fixture — load the JSON once
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_rules() -> list[dict]:
    """Load the default rules from the seed JSON file."""
    path = SEEDS_DIR / "rules.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)["items"]


@pytest.fixture
def seeded_rules(client, seed_rules) -> list[dict]:
    """Create all seed rules via the API and return API responses."""
    created = []
    for rule_data in seed_rules:
        resp = client.post(RULES_URL, json=rule_data)
        assert resp.status_code == 201, f"Failed to create '{rule_data['name']}': {resp.text}"
        created.append(resp.json())
    return created


# ---------------------------------------------------------------------------
# Seed file integrity tests
# ---------------------------------------------------------------------------

class TestSeedFileIntegrity:
    """Verify the seed JSON file matches the spec."""

    def test_seed_file_exists(self):
        assert (SEEDS_DIR / "rules.json").exists()

    def test_seed_file_has_four_rules(self, seed_rules):
        assert len(seed_rules) == 4

    def test_all_seed_rules_have_is_default_true(self, seed_rules):
        for rule in seed_rules:
            assert rule["is_default"] is True, f"'{rule['name']}' missing is_default=True"

    def test_all_seed_rules_have_enabled_true(self, seed_rules):
        for rule in seed_rules:
            assert rule["enabled"] is True, f"'{rule['name']}' missing enabled=True"

    def test_all_seed_rules_have_null_entity_id(self, seed_rules):
        """All default rules are global — no entity scoping."""
        for rule in seed_rules:
            assert rule["entity_id"] is None, f"'{rule['name']}' has non-null entity_id"

    def test_seed_rule_names_are_unique(self, seed_rules):
        names = [r["name"] for r in seed_rules]
        assert len(names) == len(set(names))


class TestConsecutiveSkipAlert:
    """Verify the Consecutive Skip Alert rule matches spec."""

    @pytest.fixture
    def rule(self, seed_rules) -> dict:
        return next(r for r in seed_rules if r["name"] == "Consecutive skip alert")

    def test_entity_type(self, rule):
        assert rule["entity_type"] == "habit"

    def test_metric(self, rule):
        assert rule["metric"] == "consecutive_skips"

    def test_operator(self, rule):
        assert rule["operator"] == ">="

    def test_threshold(self, rule):
        assert rule["threshold"] == 5

    def test_notification_type(self, rule):
        assert rule["notification_type"] == "pattern_observation"

    def test_cooldown_hours(self, rule):
        assert rule["cooldown_hours"] == 72

    def test_message_template(self, rule):
        assert rule["message_template"] == (
            "You've skipped {entity_name} {metric_value} times in a row. "
            "Want to talk about what's getting in the way?"
        )


class TestNonResponseAlert:
    """Verify the Non-Response Alert rule matches spec."""

    @pytest.fixture
    def rule(self, seed_rules) -> dict:
        return next(r for r in seed_rules if r["name"] == "Non-response alert")

    def test_entity_type(self, rule):
        assert rule["entity_type"] == "habit"

    def test_metric(self, rule):
        assert rule["metric"] == "non_responses"

    def test_operator(self, rule):
        assert rule["operator"] == ">="

    def test_threshold(self, rule):
        assert rule["threshold"] == 3

    def test_notification_type(self, rule):
        assert rule["notification_type"] == "pattern_observation"

    def test_cooldown_hours(self, rule):
        assert rule["cooldown_hours"] == 48

    def test_message_template(self, rule):
        assert rule["message_template"] == (
            "{entity_name} has had {metric_value} notifications with no response. "
            "Are the notifications reaching you at the right time?"
        )


class TestStaleTaskNudge:
    """Verify the Stale Task Nudge rule matches spec."""

    @pytest.fixture
    def rule(self, seed_rules) -> dict:
        return next(r for r in seed_rules if r["name"] == "Stale task nudge")

    def test_entity_type(self, rule):
        assert rule["entity_type"] == "task"

    def test_metric(self, rule):
        assert rule["metric"] == "days_untouched"

    def test_operator(self, rule):
        assert rule["operator"] == ">="

    def test_threshold(self, rule):
        assert rule["threshold"] == 14

    def test_notification_type(self, rule):
        assert rule["notification_type"] == "stale_work_nudge"

    def test_cooldown_hours(self, rule):
        assert rule["cooldown_hours"] == 168

    def test_message_template(self, rule):
        assert rule["message_template"] == (
            "{entity_name} hasn't been touched in {metric_value} days. "
            "Still on your radar?"
        )


class TestStreakBreakNotice:
    """Verify the Streak Break Notice rule matches spec."""

    @pytest.fixture
    def rule(self, seed_rules) -> dict:
        return next(r for r in seed_rules if r["name"] == "Streak break notice")

    def test_entity_type(self, rule):
        assert rule["entity_type"] == "habit"

    def test_metric(self, rule):
        assert rule["metric"] == "streak_length"

    def test_operator(self, rule):
        assert rule["operator"] == ">="

    def test_threshold(self, rule):
        assert rule["threshold"] == 7

    def test_notification_type(self, rule):
        assert rule["notification_type"] == "pattern_observation"

    def test_cooldown_hours(self, rule):
        assert rule["cooldown_hours"] == 168

    def test_message_template(self, rule):
        assert rule["message_template"] == (
            "Your {entity_name} streak of {metric_value} days just ended. "
            "That's still real progress \u2014 want to restart?"
        )


# ---------------------------------------------------------------------------
# Template validation tests — all seed templates pass placeholder validation
# ---------------------------------------------------------------------------

class TestSeedTemplatesValid:
    """All seed message templates use only allowed placeholders."""

    def test_all_templates_pass_validation(self, seed_rules):
        for rule in seed_rules:
            result = validate_message_template(rule["message_template"])
            assert result == rule["message_template"], (
                f"Template validation changed '{rule['name']}' template"
            )

    def test_all_templates_parse_as_rule_create(self, seed_rules):
        """Each seed rule produces a valid RuleCreate schema."""
        for rule_data in seed_rules:
            schema = RuleCreate(**rule_data)
            assert schema.name == rule_data["name"]


# ---------------------------------------------------------------------------
# is_default column — model and API tests
# ---------------------------------------------------------------------------

class TestIsDefaultColumn:
    """Tests for the is_default boolean column on rules."""

    def test_is_default_false_by_default_via_api(self, client):
        """Rules created without is_default get False."""
        payload = {
            "name": "User rule",
            "entity_type": "habit",
            "metric": "consecutive_skips",
            "operator": ">=",
            "threshold": 3,
            "notification_type": "habit_nudge",
            "message_template": "{entity_name} test",
        }
        resp = client.post(RULES_URL, json=payload)
        assert resp.status_code == 201
        assert resp.json()["is_default"] is False

    def test_is_default_true_when_set(self, client):
        """Rules created with is_default=True persist the value."""
        payload = {
            "name": "Default rule",
            "entity_type": "habit",
            "metric": "consecutive_skips",
            "operator": ">=",
            "threshold": 5,
            "notification_type": "pattern_observation",
            "message_template": "{entity_name} test",
            "is_default": True,
        }
        resp = client.post(RULES_URL, json=payload)
        assert resp.status_code == 201
        assert resp.json()["is_default"] is True

    def test_is_default_in_read_schema(self, client):
        """RuleRead includes is_default field."""
        payload = {
            "name": "Read test",
            "entity_type": "task",
            "metric": "days_untouched",
            "operator": ">=",
            "threshold": 7,
            "notification_type": "stale_work_nudge",
            "message_template": "{entity_name} test",
            "is_default": True,
        }
        created = client.post(RULES_URL, json=payload).json()
        resp = client.get(f"{RULES_URL}/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["is_default"] is True

    def test_is_default_model_default(self, db):
        """ORM model defaults is_default to False."""
        rule = Rule(
            name="ORM test",
            entity_type=RuleEntityType.habit,
            metric=RuleMetric.consecutive_skips,
            operator=RuleOperator.gte,
            threshold=3,
            action=RuleAction.create_notification,
            notification_type="habit_nudge",
            message_template="test",
            enabled=True,
            cooldown_hours=24,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        assert rule.is_default is False


# ---------------------------------------------------------------------------
# is_default list filter
# ---------------------------------------------------------------------------

class TestIsDefaultFilter:
    """GET /api/rules?is_default=true|false filters correctly."""

    def test_filter_is_default_true(self, client, seeded_rules):
        """Filtering by is_default=true returns only defaults."""
        # Add a user-created rule
        client.post(RULES_URL, json={
            "name": "User custom",
            "entity_type": "habit",
            "metric": "consecutive_skips",
            "operator": ">=",
            "threshold": 10,
            "notification_type": "habit_nudge",
            "message_template": "{entity_name} custom",
        })

        resp = client.get(RULES_URL, params={"is_default": "true"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        assert all(r["is_default"] is True for r in data)

    def test_filter_is_default_false(self, client, seeded_rules):
        """Filtering by is_default=false returns only user-created rules."""
        client.post(RULES_URL, json={
            "name": "User custom",
            "entity_type": "habit",
            "metric": "consecutive_skips",
            "operator": ">=",
            "threshold": 10,
            "notification_type": "habit_nudge",
            "message_template": "{entity_name} custom",
        })

        resp = client.get(RULES_URL, params={"is_default": "false"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "User custom"
        assert data[0]["is_default"] is False


# ---------------------------------------------------------------------------
# Seed creation via API — verifies rules round-trip correctly
# ---------------------------------------------------------------------------

class TestSeedCreationViaAPI:
    """Seed rules created via POST /api/rules match spec values."""

    def test_creates_four_rules(self, seeded_rules):
        assert len(seeded_rules) == 4

    def test_all_have_is_default_true(self, seeded_rules):
        for rule in seeded_rules:
            assert rule["is_default"] is True

    def test_all_have_enabled_true(self, seeded_rules):
        for rule in seeded_rules:
            assert rule["enabled"] is True

    def test_all_fetchable_by_id(self, client, seeded_rules):
        """Each seeded rule can be fetched via GET /api/rules/{id}."""
        for rule in seeded_rules:
            resp = client.get(f"{RULES_URL}/{rule['id']}")
            assert resp.status_code == 200
            assert resp.json()["name"] == rule["name"]

    def test_list_with_enabled_true_returns_all_defaults(self, client, seeded_rules):
        """GET /api/rules?enabled=true returns all 4 default rules."""
        resp = client.get(RULES_URL, params={"enabled": "true"})
        assert resp.status_code == 200
        assert len(resp.json()) == 4


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------

class TestSeedIdempotency:
    """Running the seed twice produces exactly 4 rules — no duplicates."""

    def test_duplicate_name_rejected_at_db_level(self, db):
        """Inserting a rule with a duplicate name raises IntegrityError."""
        from sqlalchemy.exc import IntegrityError as SAIntegrityError

        base = dict(
            entity_type=RuleEntityType.habit,
            metric=RuleMetric.consecutive_skips,
            operator=RuleOperator.gte,
            threshold=5,
            action=RuleAction.create_notification,
            notification_type="pattern_observation",
            message_template="test",
            enabled=True,
            cooldown_hours=24,
        )
        db.add(Rule(name="Duplicate test", **base))
        db.commit()

        db.add(Rule(name="Duplicate test", **base))
        with pytest.raises(SAIntegrityError):
            db.commit()
        db.rollback()

    def test_seed_twice_still_four_rules(self, client, seed_rules):
        """Seeding, then seeding again (skipping existing), yields exactly 4."""
        # First pass — create all
        for rule_data in seed_rules:
            resp = client.post(RULES_URL, json=rule_data)
            assert resp.status_code == 201

        # Verify 4 rules
        resp = client.get(RULES_URL)
        assert len(resp.json()) == 4

        # Second pass — skip existing (simulates seed script behavior)
        existing = {r["name"] for r in client.get(RULES_URL).json()}
        created_count = 0
        for rule_data in seed_rules:
            if rule_data["name"] not in existing:
                resp = client.post(RULES_URL, json=rule_data)
                assert resp.status_code == 201
                created_count += 1

        assert created_count == 0

        # Still exactly 4 rules
        resp = client.get(RULES_URL)
        assert len(resp.json()) == 4


# ---------------------------------------------------------------------------
# Unique name constraint tests
# ---------------------------------------------------------------------------

class TestUniqueNameConstraint:
    """The unique constraint on rules.name prevents duplicates at the DB level."""

    def test_unique_names_allowed(self, client):
        """Two rules with different names succeed."""
        base = {
            "entity_type": "habit",
            "metric": "consecutive_skips",
            "operator": ">=",
            "threshold": 3,
            "notification_type": "habit_nudge",
            "message_template": "{entity_name} test",
        }
        resp1 = client.post(RULES_URL, json={**base, "name": "Rule A"})
        resp2 = client.post(RULES_URL, json={**base, "name": "Rule B"})
        assert resp1.status_code == 201
        assert resp2.status_code == 201
