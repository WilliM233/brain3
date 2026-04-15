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

"""Tests for the Rule model, schemas, and FK constraint on notification_queue."""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models import NotificationQueue, Rule
from app.schemas.rule import (
    ALLOWED_PLACEHOLDERS,
    RuleAction,
    RuleCreate,
    RuleEntityType,
    RuleMetric,
    RuleOperator,
    RuleRead,
    RuleUpdate,
    validate_message_template,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rule(**overrides) -> Rule:
    """Build a Rule ORM instance with sensible defaults."""
    defaults = {
        "id": uuid.uuid4(),
        "name": "Skip alert",
        "entity_type": RuleEntityType.habit,
        "metric": RuleMetric.consecutive_skips,
        "operator": RuleOperator.gte,
        "threshold": 3,
        "action": RuleAction.create_notification,
        "notification_type": "habit_nudge",
        "message_template": "{entity_name} has been skipped {metric_value} times",
        "enabled": True,
        "cooldown_hours": 24,
    }
    defaults.update(overrides)
    return Rule(**defaults)


def _persist(db, obj):
    """Add, commit, and refresh an ORM object."""
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _make_notification(db, **overrides) -> NotificationQueue:
    """Create and persist a NotificationQueue row."""
    defaults = {
        "id": uuid.uuid4(),
        "notification_type": "habit_nudge",
        "delivery_type": "notification",
        "status": "pending",
        "scheduled_at": datetime.now(timezone.utc),
        "target_entity_type": "habit",
        "target_entity_id": uuid.uuid4(),
        "message": "Test notification",
        "scheduled_by": "system",
    }
    defaults.update(overrides)
    nq = NotificationQueue(**defaults)
    db.add(nq)
    db.commit()
    db.refresh(nq)
    return nq


# ---------------------------------------------------------------------------
# Enum value tests
# ---------------------------------------------------------------------------

class TestEnumValues:
    """Verify enum members and their values match the spec."""

    def test_rule_entity_type_members(self):
        assert set(RuleEntityType) == {
            RuleEntityType.habit,
            RuleEntityType.task,
            RuleEntityType.routine,
            RuleEntityType.checkin,
        }
        assert RuleEntityType.habit.value == "habit"
        assert RuleEntityType.task.value == "task"
        assert RuleEntityType.routine.value == "routine"
        assert RuleEntityType.checkin.value == "checkin"

    def test_rule_metric_members(self):
        assert set(RuleMetric) == {
            RuleMetric.consecutive_skips,
            RuleMetric.days_untouched,
            RuleMetric.non_responses,
            RuleMetric.streak_length,
        }
        assert RuleMetric.consecutive_skips.value == "consecutive_skips"
        assert RuleMetric.days_untouched.value == "days_untouched"
        assert RuleMetric.non_responses.value == "non_responses"
        assert RuleMetric.streak_length.value == "streak_length"

    def test_rule_operator_members(self):
        assert set(RuleOperator) == {
            RuleOperator.gte,
            RuleOperator.lte,
            RuleOperator.eq,
        }
        assert RuleOperator.gte.value == ">="
        assert RuleOperator.lte.value == "<="
        assert RuleOperator.eq.value == "=="

    def test_rule_action_members(self):
        assert set(RuleAction) == {RuleAction.create_notification}
        assert RuleAction.create_notification.value == "create_notification"


# ---------------------------------------------------------------------------
# Model instantiation and round-trip tests
# ---------------------------------------------------------------------------

class TestRuleModel:
    """Rule ORM model — instantiation, defaults, and database round-trips."""

    def test_create_rule_with_all_fields(self, db):
        rule = _make_rule()
        persisted = _persist(db, rule)

        assert persisted.name == "Skip alert"
        assert persisted.entity_type == RuleEntityType.habit
        assert persisted.entity_id is None
        assert persisted.metric == RuleMetric.consecutive_skips
        assert persisted.operator == RuleOperator.gte
        assert persisted.threshold == 3
        assert persisted.action == RuleAction.create_notification
        assert persisted.notification_type == "habit_nudge"
        assert persisted.enabled is True
        assert persisted.cooldown_hours == 24
        assert persisted.last_triggered_at is None

    def test_round_trip_all_fields(self, db):
        """Create, persist, re-query — all fields survive."""
        rule_id = uuid.uuid4()
        entity_id = uuid.uuid4()
        rule = _make_rule(
            id=rule_id,
            entity_id=entity_id,
            operator=RuleOperator.lte,
            threshold=5,
            metric=RuleMetric.days_untouched,
            notification_type="stale_work_nudge",
        )
        _persist(db, rule)

        fetched = db.get(Rule, rule_id)
        assert fetched is not None
        assert fetched.entity_id == entity_id
        assert fetched.operator == RuleOperator.lte
        assert fetched.threshold == 5
        assert fetched.metric == RuleMetric.days_untouched
        assert fetched.notification_type == "stale_work_nudge"

    def test_entity_id_nullable(self, db):
        """entity_id can be NULL (global rule)."""
        rule = _make_rule(entity_id=None)
        persisted = _persist(db, rule)
        assert persisted.entity_id is None

    def test_entity_id_with_value(self, db):
        """entity_id can reference a specific entity."""
        eid = uuid.uuid4()
        rule = _make_rule(entity_id=eid)
        persisted = _persist(db, rule)
        assert persisted.entity_id == eid

    def test_all_entity_types_persist(self, db):
        """Each RuleEntityType value round-trips."""
        for et in RuleEntityType:
            rule = _make_rule(id=uuid.uuid4(), name=f"Rule {et.value}", entity_type=et)
            persisted = _persist(db, rule)
            assert persisted.entity_type == et

    def test_all_metrics_persist(self, db):
        """Each RuleMetric value round-trips."""
        for m in RuleMetric:
            rule = _make_rule(id=uuid.uuid4(), name=f"Rule {m.value}", metric=m)
            persisted = _persist(db, rule)
            assert persisted.metric == m

    def test_all_operators_persist(self, db):
        """Each RuleOperator value round-trips."""
        for op in RuleOperator:
            rule = _make_rule(id=uuid.uuid4(), name=f"Rule {op.value}", operator=op)
            persisted = _persist(db, rule)
            assert persisted.operator == op


# ---------------------------------------------------------------------------
# FK constraint: notification_queue.rule_id → rules.id
# ---------------------------------------------------------------------------

class TestNotificationRuleFK:
    """FK constraint between notification_queue.rule_id and rules.id."""

    def test_notification_with_null_rule_id(self, db):
        """Inserting a notification with NULL rule_id succeeds."""
        nq = _make_notification(db, rule_id=None)
        assert nq.rule_id is None

    def test_notification_with_valid_rule_id(self, db):
        """Inserting a notification referencing an existing rule succeeds."""
        rule = _make_rule()
        _persist(db, rule)

        nq = _make_notification(db, rule_id=rule.id)
        assert nq.rule_id == rule.id

    def test_notification_with_nonexistent_rule_id_fails(self, db):
        """Inserting a notification with a non-existent rule_id raises."""
        fake_id = uuid.uuid4()
        nq = NotificationQueue(
            id=uuid.uuid4(),
            notification_type="habit_nudge",
            delivery_type="notification",
            status="pending",
            scheduled_at=datetime.now(timezone.utc),
            target_entity_type="habit",
            target_entity_id=uuid.uuid4(),
            message="Test",
            scheduled_by="system",
            rule_id=fake_id,
        )
        db.add(nq)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_delete_rule_sets_notification_rule_id_null(self, db):
        """Deleting a rule sets linked notifications' rule_id to NULL."""
        rule = _make_rule()
        _persist(db, rule)
        nq = _make_notification(db, rule_id=rule.id)
        assert nq.rule_id == rule.id

        db.delete(rule)
        db.commit()
        db.refresh(nq)
        assert nq.rule_id is None


# ---------------------------------------------------------------------------
# Template placeholder validation (schema-level)
# ---------------------------------------------------------------------------

class TestTemplatePlaceholderValidation:
    """validate_message_template rejects unknown placeholders."""

    def test_valid_template_all_placeholders(self):
        template = (
            "{rule_name}: {entity_type} '{entity_name}' hit "
            "{metric_value} (threshold {threshold})"
        )
        result = validate_message_template(template)
        assert result == template

    def test_valid_template_no_placeholders(self):
        """Plain text with no placeholders is valid."""
        result = validate_message_template("Something happened")
        assert result == "Something happened"

    def test_valid_template_subset_of_placeholders(self):
        result = validate_message_template("{entity_name} skipped")
        assert result == "{entity_name} skipped"

    def test_invalid_placeholder_rejected(self):
        with pytest.raises(ValueError, match="Unknown placeholder"):
            validate_message_template("{bad_field} is not allowed")

    def test_mixed_valid_and_invalid_rejected(self):
        with pytest.raises(ValueError, match="Unknown placeholder"):
            validate_message_template("{entity_name} {nope}")

    def test_each_allowed_placeholder_individually(self):
        for ph in ALLOWED_PLACEHOLDERS:
            result = validate_message_template(f"{{{ph}}}")
            assert result == f"{{{ph}}}"

    def test_escaped_braces_ignored(self):
        """Literal {{ and }} are not treated as placeholders."""
        result = validate_message_template("Literal {{braces}} are fine")
        assert result == "Literal {{braces}} are fine"


# ---------------------------------------------------------------------------
# Pydantic schema tests — RuleCreate
# ---------------------------------------------------------------------------

class TestRuleCreateSchema:
    """RuleCreate validation."""

    def test_valid_create(self):
        data = {
            "name": "Skip alert",
            "entity_type": "habit",
            "metric": "consecutive_skips",
            "operator": ">=",
            "threshold": 3,
            "notification_type": "habit_nudge",
            "message_template": "{entity_name} skipped {metric_value} times",
        }
        schema = RuleCreate(**data)
        assert schema.name == "Skip alert"
        assert schema.entity_type == RuleEntityType.habit
        assert schema.operator == RuleOperator.gte
        assert schema.action == RuleAction.create_notification
        assert schema.enabled is True
        assert schema.cooldown_hours == 24

    def test_defaults_applied(self):
        data = {
            "name": "Test",
            "entity_type": "task",
            "metric": "days_untouched",
            "operator": "<=",
            "threshold": 7,
            "notification_type": "stale_work_nudge",
            "message_template": "Hello",
        }
        schema = RuleCreate(**data)
        assert schema.action == RuleAction.create_notification
        assert schema.enabled is True
        assert schema.cooldown_hours == 24
        assert schema.entity_id is None

    def test_invalid_template_rejected(self):
        data = {
            "name": "Bad template",
            "entity_type": "habit",
            "metric": "consecutive_skips",
            "operator": ">=",
            "threshold": 3,
            "notification_type": "habit_nudge",
            "message_template": "{unknown_placeholder}",
        }
        with pytest.raises(ValidationError, match="Unknown placeholder"):
            RuleCreate(**data)

    def test_empty_name_rejected(self):
        data = {
            "name": "",
            "entity_type": "habit",
            "metric": "consecutive_skips",
            "operator": ">=",
            "threshold": 3,
            "notification_type": "habit_nudge",
            "message_template": "Hello",
        }
        with pytest.raises(ValidationError):
            RuleCreate(**data)

    def test_invalid_entity_type_rejected(self):
        data = {
            "name": "Test",
            "entity_type": "invalid",
            "metric": "consecutive_skips",
            "operator": ">=",
            "threshold": 3,
            "notification_type": "habit_nudge",
            "message_template": "Hello",
        }
        with pytest.raises(ValidationError):
            RuleCreate(**data)

    def test_invalid_notification_type_rejected(self):
        data = {
            "name": "Test",
            "entity_type": "habit",
            "metric": "consecutive_skips",
            "operator": ">=",
            "threshold": 3,
            "notification_type": "invalid_type",
            "message_template": "Hello",
        }
        with pytest.raises(ValidationError):
            RuleCreate(**data)


# ---------------------------------------------------------------------------
# Pydantic schema tests — RuleUpdate
# ---------------------------------------------------------------------------

class TestRuleUpdateSchema:
    """RuleUpdate validation — all fields optional."""

    def test_empty_update(self):
        schema = RuleUpdate()
        assert schema.name is None
        assert schema.entity_type is None

    def test_partial_update(self):
        schema = RuleUpdate(name="New name", threshold=5)
        assert schema.name == "New name"
        assert schema.threshold == 5
        assert schema.metric is None

    def test_update_template_validated(self):
        with pytest.raises(ValidationError, match="Unknown placeholder"):
            RuleUpdate(message_template="{invalid}")

    def test_update_valid_template(self):
        schema = RuleUpdate(message_template="{entity_name} updated")
        assert schema.message_template == "{entity_name} updated"


# ---------------------------------------------------------------------------
# Pydantic schema tests — RuleRead
# ---------------------------------------------------------------------------

class TestRuleReadSchema:
    """RuleRead from_attributes mapping."""

    def test_from_orm_object(self, db):
        rule = _make_rule()
        persisted = _persist(db, rule)

        read = RuleRead.model_validate(persisted)
        assert read.id == persisted.id
        assert read.name == "Skip alert"
        assert read.entity_type == RuleEntityType.habit
        assert read.operator == RuleOperator.gte
        assert read.threshold == 3
        assert read.enabled is True
        assert read.last_triggered_at is None


# ===========================================================================
# API endpoint tests — [2F-02]
# ===========================================================================

RULES_URL = "/api/rules"


def _rule_payload(**overrides) -> dict:
    """Build a valid rule creation payload."""
    defaults = {
        "name": "Skip alert",
        "entity_type": "habit",
        "metric": "consecutive_skips",
        "operator": ">=",
        "threshold": 3,
        "notification_type": "habit_nudge",
        "message_template": "{entity_name} has been skipped {metric_value} times",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# POST /api/rules — create
# ---------------------------------------------------------------------------

class TestCreateRuleEndpoint:
    """POST /api/rules"""

    def test_create_rule_happy_path(self, client):
        payload = _rule_payload()
        resp = client.post(RULES_URL, json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Skip alert"
        assert data["entity_type"] == "habit"
        assert data["metric"] == "consecutive_skips"
        assert data["operator"] == ">="
        assert data["threshold"] == 3
        assert data["notification_type"] == "habit_nudge"
        assert data["enabled"] is True
        assert data["cooldown_hours"] == 24
        assert data["action"] == "create_notification"
        assert data["last_triggered_at"] is None
        assert data["id"] is not None
        assert data["created_at"] is not None

    def test_create_rule_with_entity_id(self, client):
        eid = str(uuid.uuid4())
        resp = client.post(RULES_URL, json=_rule_payload(entity_id=eid))
        assert resp.status_code == 201
        assert resp.json()["entity_id"] == eid

    def test_create_rule_with_all_optional_overrides(self, client):
        resp = client.post(RULES_URL, json=_rule_payload(
            enabled=False,
            cooldown_hours=48,
        ))
        assert resp.status_code == 201
        data = resp.json()
        assert data["enabled"] is False
        assert data["cooldown_hours"] == 48

    def test_create_rule_invalid_template_returns_422(self, client):
        resp = client.post(RULES_URL, json=_rule_payload(
            message_template="{bad_placeholder} is invalid",
        ))
        assert resp.status_code == 422

    def test_create_rule_invalid_entity_type_returns_422(self, client):
        resp = client.post(RULES_URL, json=_rule_payload(entity_type="invalid"))
        assert resp.status_code == 422

    def test_create_rule_invalid_metric_returns_422(self, client):
        resp = client.post(RULES_URL, json=_rule_payload(metric="invalid"))
        assert resp.status_code == 422

    def test_create_rule_invalid_operator_returns_422(self, client):
        resp = client.post(RULES_URL, json=_rule_payload(operator="!="))
        assert resp.status_code == 422

    def test_create_rule_invalid_notification_type_returns_422(self, client):
        resp = client.post(RULES_URL, json=_rule_payload(
            notification_type="invalid_type",
        ))
        assert resp.status_code == 422

    def test_create_rule_missing_required_field_returns_422(self, client):
        payload = _rule_payload()
        del payload["name"]
        resp = client.post(RULES_URL, json=payload)
        assert resp.status_code == 422

    def test_create_rule_empty_name_returns_422(self, client):
        resp = client.post(RULES_URL, json=_rule_payload(name=""))
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/rules — list with filters
# ---------------------------------------------------------------------------

class TestListRulesEndpoint:
    """GET /api/rules"""

    def test_list_empty(self, client):
        resp = client.get(RULES_URL)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created_rules(self, client):
        client.post(RULES_URL, json=_rule_payload(name="Rule A"))
        client.post(RULES_URL, json=_rule_payload(name="Rule B"))
        resp = client.get(RULES_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_ordered_by_created_at_desc(self, client, db):
        """Newest rule appears first in the list."""
        from datetime import datetime, timezone

        from app.models import Rule as RuleModel
        from app.schemas.rule import (
            RuleAction as RA,
        )
        from app.schemas.rule import (
            RuleEntityType as RET,
        )
        from app.schemas.rule import (
            RuleMetric as RM,
        )
        from app.schemas.rule import (
            RuleOperator as RO,
        )

        earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
        later = datetime(2026, 1, 2, tzinfo=timezone.utc)

        r1 = RuleModel(
            name="First", entity_type=RET.habit, metric=RM.consecutive_skips,
            operator=RO.gte, threshold=3, action=RA.create_notification,
            notification_type="habit_nudge", message_template="hi",
            enabled=True, cooldown_hours=24, created_at=earlier, updated_at=earlier,
        )
        r2 = RuleModel(
            name="Second", entity_type=RET.habit, metric=RM.consecutive_skips,
            operator=RO.gte, threshold=3, action=RA.create_notification,
            notification_type="habit_nudge", message_template="hi",
            enabled=True, cooldown_hours=24, created_at=later, updated_at=later,
        )
        db.add_all([r1, r2])
        db.commit()

        resp = client.get(RULES_URL)
        names = [r["name"] for r in resp.json()]
        assert names == ["Second", "First"]

    def test_filter_by_entity_type(self, client):
        client.post(RULES_URL, json=_rule_payload(
            name="Habit rule", entity_type="habit",
        ))
        client.post(RULES_URL, json=_rule_payload(
            name="Task rule", entity_type="task",
            metric="days_untouched",
            notification_type="stale_work_nudge",
        ))
        resp = client.get(RULES_URL, params={"entity_type": "task"})
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Task rule"

    def test_filter_by_enabled(self, client):
        client.post(RULES_URL, json=_rule_payload(name="Active", enabled=True))
        client.post(RULES_URL, json=_rule_payload(name="Disabled", enabled=False))
        resp = client.get(RULES_URL, params={"enabled": "false"})
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Disabled"

    def test_filter_by_notification_type(self, client):
        client.post(RULES_URL, json=_rule_payload(
            name="Nudge", notification_type="habit_nudge",
        ))
        client.post(RULES_URL, json=_rule_payload(
            name="Stale", entity_type="task", metric="days_untouched",
            notification_type="stale_work_nudge",
        ))
        resp = client.get(RULES_URL, params={
            "notification_type": "stale_work_nudge",
        })
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Stale"

    def test_filter_by_entity_id(self, client):
        eid = str(uuid.uuid4())
        client.post(RULES_URL, json=_rule_payload(name="Scoped", entity_id=eid))
        client.post(RULES_URL, json=_rule_payload(name="Global"))
        resp = client.get(RULES_URL, params={"entity_id": eid})
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Scoped"

    def test_filter_combined(self, client):
        """Multiple filters compose with AND logic."""
        client.post(RULES_URL, json=_rule_payload(
            name="Match", entity_type="habit", enabled=True,
        ))
        client.post(RULES_URL, json=_rule_payload(
            name="Wrong type", entity_type="task", enabled=True,
            metric="days_untouched", notification_type="stale_work_nudge",
        ))
        client.post(RULES_URL, json=_rule_payload(
            name="Disabled", entity_type="habit", enabled=False,
        ))
        resp = client.get(RULES_URL, params={
            "entity_type": "habit", "enabled": "true",
        })
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Match"


# ---------------------------------------------------------------------------
# GET /api/rules/{rule_id} — detail
# ---------------------------------------------------------------------------

class TestGetRuleEndpoint:
    """GET /api/rules/{rule_id}"""

    def test_get_rule_happy_path(self, client):
        created = client.post(RULES_URL, json=_rule_payload()).json()
        resp = client.get(f"{RULES_URL}/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]
        assert resp.json()["name"] == "Skip alert"

    def test_get_rule_not_found(self, client):
        fake = str(uuid.uuid4())
        resp = client.get(f"{RULES_URL}/{fake}")
        assert resp.status_code == 404

    def test_get_rule_invalid_uuid(self, client):
        resp = client.get(f"{RULES_URL}/not-a-uuid")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/rules/{rule_id} — update
# ---------------------------------------------------------------------------

class TestUpdateRuleEndpoint:
    """PATCH /api/rules/{rule_id}"""

    def test_update_name(self, client):
        created = client.post(RULES_URL, json=_rule_payload()).json()
        resp = client.patch(f"{RULES_URL}/{created['id']}", json={"name": "New name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New name"

    def test_update_threshold(self, client):
        created = client.post(RULES_URL, json=_rule_payload()).json()
        resp = client.patch(
            f"{RULES_URL}/{created['id']}", json={"threshold": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["threshold"] == 10

    def test_update_enabled(self, client):
        created = client.post(RULES_URL, json=_rule_payload()).json()
        resp = client.patch(
            f"{RULES_URL}/{created['id']}", json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_update_template_validated(self, client):
        created = client.post(RULES_URL, json=_rule_payload()).json()
        resp = client.patch(
            f"{RULES_URL}/{created['id']}",
            json={"message_template": "{bad_placeholder}"},
        )
        assert resp.status_code == 422

    def test_update_valid_template(self, client):
        created = client.post(RULES_URL, json=_rule_payload()).json()
        resp = client.patch(
            f"{RULES_URL}/{created['id']}",
            json={"message_template": "{entity_name} updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["message_template"] == "{entity_name} updated"

    def test_update_not_found(self, client):
        fake = str(uuid.uuid4())
        resp = client.patch(f"{RULES_URL}/{fake}", json={"name": "Nope"})
        assert resp.status_code == 404

    def test_update_multiple_fields(self, client):
        created = client.post(RULES_URL, json=_rule_payload()).json()
        resp = client.patch(
            f"{RULES_URL}/{created['id']}",
            json={"name": "Updated", "threshold": 5, "cooldown_hours": 48},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated"
        assert data["threshold"] == 5
        assert data["cooldown_hours"] == 48

    def test_update_empty_body_is_noop(self, client):
        created = client.post(RULES_URL, json=_rule_payload()).json()
        resp = client.patch(f"{RULES_URL}/{created['id']}", json={})
        assert resp.status_code == 200
        assert resp.json()["name"] == created["name"]


# ---------------------------------------------------------------------------
# DELETE /api/rules/{rule_id}
# ---------------------------------------------------------------------------

class TestDeleteRuleEndpoint:
    """DELETE /api/rules/{rule_id}"""

    def test_delete_rule_happy_path(self, client):
        created = client.post(RULES_URL, json=_rule_payload()).json()
        resp = client.delete(f"{RULES_URL}/{created['id']}")
        assert resp.status_code == 204
        # Confirm it's gone
        resp = client.get(f"{RULES_URL}/{created['id']}")
        assert resp.status_code == 404

    def test_delete_rule_not_found(self, client):
        fake = str(uuid.uuid4())
        resp = client.delete(f"{RULES_URL}/{fake}")
        assert resp.status_code == 404

    def test_delete_rule_sets_notification_rule_id_null(self, client, db):
        """FK cascade: deleting a rule NULLs notification_queue.rule_id."""
        # Create rule via API
        created = client.post(RULES_URL, json=_rule_payload()).json()
        rule_id = created["id"]

        # Create notification linked to the rule (convert str to UUID)
        nq = _make_notification(db, rule_id=uuid.UUID(rule_id))
        assert str(nq.rule_id) == rule_id

        # Delete the rule
        resp = client.delete(f"{RULES_URL}/{rule_id}")
        assert resp.status_code == 204

        # Verify notification's rule_id is now NULL
        db.refresh(nq)
        assert nq.rule_id is None


# ---------------------------------------------------------------------------
# Full lifecycle test
# ---------------------------------------------------------------------------

class TestRuleLifecycle:
    """End-to-end CRUD lifecycle through the API."""

    def test_create_read_update_delete(self, client):
        # Create
        resp = client.post(RULES_URL, json=_rule_payload())
        assert resp.status_code == 201
        rule_id = resp.json()["id"]

        # Read
        resp = client.get(f"{RULES_URL}/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Skip alert"

        # List
        resp = client.get(RULES_URL)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        # Update
        resp = client.patch(
            f"{RULES_URL}/{rule_id}",
            json={"name": "Updated alert", "threshold": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated alert"
        assert resp.json()["threshold"] == 5

        # Delete
        resp = client.delete(f"{RULES_URL}/{rule_id}")
        assert resp.status_code == 204

        # Confirm gone
        resp = client.get(RULES_URL)
        assert resp.json() == []
