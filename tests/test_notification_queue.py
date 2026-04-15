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

"""Tests for the NotificationQueue model — instantiation, defaults, and constraints."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import NotificationQueue, Rule
from app.schemas.rule import RuleAction, RuleEntityType, RuleMetric, RuleOperator

# ---------------------------------------------------------------------------
# Valid notification types, statuses, delivery types, and scheduled_by values
# ---------------------------------------------------------------------------

VALID_NOTIFICATION_TYPES = [
    "habit_nudge",
    "routine_checklist",
    "checkin_prompt",
    "time_block_reminder",
    "deadline_event_alert",
    "pattern_observation",
    "stale_work_nudge",
]

VALID_STATUSES = ["pending", "delivered", "responded", "expired"]

VALID_DELIVERY_TYPES = ["notification"]

VALID_SCHEDULED_BY = ["system", "claude", "rule"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_notification(**overrides) -> NotificationQueue:
    """Build a NotificationQueue instance with sensible defaults."""
    defaults = {
        "id": uuid.uuid4(),
        "notification_type": "habit_nudge",
        "delivery_type": "notification",
        "status": "pending",
        "scheduled_at": datetime.now(timezone.utc),
        "target_entity_type": "habit",
        "target_entity_id": uuid.uuid4(),
        "message": "Time to stretch!",
        "scheduled_by": "system",
    }
    defaults.update(overrides)
    return NotificationQueue(**defaults)


def _persist(db, notification: NotificationQueue) -> NotificationQueue:
    """Add, commit, and refresh a notification in the test DB."""
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


# ---------------------------------------------------------------------------
# Model instantiation tests
# ---------------------------------------------------------------------------

class TestNotificationQueueModel:
    """NotificationQueue model can be instantiated and persisted."""

    def test_create_minimal_notification(self, db):
        """A notification with only required fields persists correctly."""
        n = _make_notification()
        result = _persist(db, n)

        assert result.id is not None
        assert result.notification_type == "habit_nudge"
        assert result.delivery_type == "notification"
        assert result.status == "pending"
        assert result.message == "Time to stretch!"
        assert result.scheduled_by == "system"
        assert result.target_entity_type == "habit"
        assert result.target_entity_id is not None

    def test_create_notification_with_all_fields(self, db):
        """A notification with every optional field set persists correctly."""
        now = datetime.now(timezone.utc)
        rule = Rule(
            id=uuid.uuid4(), name="test rule", entity_type=RuleEntityType.habit,
            metric=RuleMetric.consecutive_skips, operator=RuleOperator.gte,
            threshold=3, action=RuleAction.create_notification,
            notification_type="habit_nudge", message_template="test",
        )
        db.add(rule)
        db.commit()
        n = _make_notification(
            canned_responses=["Done", "Skip", "Snooze"],
            response="Done",
            response_note="Felt good today",
            responded_at=now,
            expires_at=now,
            rule_id=rule.id,
        )
        result = _persist(db, n)

        assert result.canned_responses == ["Done", "Skip", "Snooze"]
        assert result.response == "Done"
        assert result.response_note == "Felt good today"
        assert result.responded_at is not None
        assert result.expires_at is not None
        assert result.rule_id == rule.id

    def test_nullable_fields_default_to_none(self, db):
        """Optional fields are None when not provided."""
        n = _make_notification()
        result = _persist(db, n)

        assert result.canned_responses is None
        assert result.response is None
        assert result.response_note is None
        assert result.responded_at is None
        assert result.expires_at is None
        assert result.rule_id is None

    def test_server_defaults_applied(self, db):
        """Server defaults for delivery_type, status, created_at, updated_at are set."""
        n = NotificationQueue(
            id=uuid.uuid4(),
            notification_type="checkin_prompt",
            scheduled_at=datetime.now(timezone.utc),
            target_entity_type="checkin",
            target_entity_id=uuid.uuid4(),
            message="How are you feeling?",
            scheduled_by="claude",
        )
        result = _persist(db, n)

        assert result.delivery_type == "notification"
        assert result.status == "pending"
        assert result.created_at is not None
        assert result.updated_at is not None


# ---------------------------------------------------------------------------
# Enum membership tests
# ---------------------------------------------------------------------------

class TestNotificationTypeValues:
    """All 7 notification types are accepted."""

    @pytest.mark.parametrize("ntype", VALID_NOTIFICATION_TYPES)
    def test_valid_notification_type(self, db, ntype):
        n = _make_notification(notification_type=ntype)
        result = _persist(db, n)
        assert result.notification_type == ntype

    def test_invalid_notification_type_rejected(self, db):
        n = _make_notification(notification_type="invalid_type")
        db.add(n)
        with pytest.raises(IntegrityError):
            db.commit()


class TestNotificationStatusValues:
    """All 4 statuses are accepted."""

    @pytest.mark.parametrize("status", VALID_STATUSES)
    def test_valid_status(self, db, status):
        n = _make_notification(status=status)
        result = _persist(db, n)
        assert result.status == status

    def test_invalid_status_rejected(self, db):
        n = _make_notification(status="cancelled")
        db.add(n)
        with pytest.raises(IntegrityError):
            db.commit()


class TestDeliveryTypeValues:
    """DeliveryType enum — currently single value."""

    @pytest.mark.parametrize("dtype", VALID_DELIVERY_TYPES)
    def test_valid_delivery_type(self, db, dtype):
        n = _make_notification(delivery_type=dtype)
        result = _persist(db, n)
        assert result.delivery_type == dtype

    def test_invalid_delivery_type_rejected(self, db):
        n = _make_notification(delivery_type="email")
        db.add(n)
        with pytest.raises(IntegrityError):
            db.commit()


class TestScheduledByValues:
    """ScheduledBy enum — system, claude, or rule."""

    @pytest.mark.parametrize("sched", VALID_SCHEDULED_BY)
    def test_valid_scheduled_by(self, db, sched):
        n = _make_notification(scheduled_by=sched)
        result = _persist(db, n)
        assert result.scheduled_by == sched

    def test_invalid_scheduled_by_rejected(self, db):
        n = _make_notification(scheduled_by="cron")
        db.add(n)
        with pytest.raises(IntegrityError):
            db.commit()


# ---------------------------------------------------------------------------
# Target entity type tests (plain string — not enum-constrained)
# ---------------------------------------------------------------------------

class TestTargetEntityType:
    """target_entity_type is a plain string, accepts any entity kind."""

    @pytest.mark.parametrize(
        "entity_type",
        ["habit", "routine", "task", "checkin", "goal", "project"],
    )
    def test_known_entity_types(self, db, entity_type):
        n = _make_notification(target_entity_type=entity_type)
        result = _persist(db, n)
        assert result.target_entity_type == entity_type

    def test_future_entity_type_accepted(self, db):
        """Plain string column accepts new entity types without migration."""
        n = _make_notification(target_entity_type="milestone")
        result = _persist(db, n)
        assert result.target_entity_type == "milestone"


# ---------------------------------------------------------------------------
# JSONB canned_responses tests
# ---------------------------------------------------------------------------

class TestCannedResponses:
    """canned_responses stores and retrieves JSON arrays correctly."""

    def test_string_array(self, db):
        n = _make_notification(canned_responses=["Yes", "No", "Maybe"])
        result = _persist(db, n)
        assert result.canned_responses == ["Yes", "No", "Maybe"]

    def test_empty_array(self, db):
        n = _make_notification(canned_responses=[])
        result = _persist(db, n)
        assert result.canned_responses == []

    def test_null_canned_responses(self, db):
        n = _make_notification()
        result = _persist(db, n)
        assert result.canned_responses is None
