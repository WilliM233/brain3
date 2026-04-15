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

"""Tests for the rule evaluation engine — [2F-03]."""

import uuid
from datetime import UTC, datetime, timedelta

from app.models import Habit, NotificationQueue, Rule, StateCheckin, Task
from app.schemas.rule import (
    RuleAction,
    RuleEntityType,
    RuleMetric,
    RuleOperator,
)
from app.services.rule_evaluation import (
    evaluate_rules,
)

RULES_URL = "/api/rules"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rule(db, **overrides) -> Rule:
    """Create and persist a rule with sensible defaults."""
    defaults = {
        "name": f"Test rule {uuid.uuid4().hex[:6]}",
        "entity_type": RuleEntityType.habit,
        "metric": RuleMetric.consecutive_skips,
        "operator": RuleOperator.gte,
        "threshold": 3,
        "action": RuleAction.create_notification,
        "notification_type": "habit_nudge",
        "message_template": "{entity_name} hit {metric_value} (threshold {threshold})",
        "enabled": True,
        "cooldown_hours": 24,
    }
    defaults.update(overrides)
    rule = Rule(**defaults)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def _make_habit_orm(db, **overrides) -> Habit:
    """Create and persist a habit directly via ORM."""
    defaults = {
        "title": "Test Habit",
        "status": "active",
        "current_streak": 0,
        "best_streak": 0,
    }
    defaults.update(overrides)
    habit = Habit(**defaults)
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit


def _make_task_orm(db, **overrides) -> Task:
    """Create and persist a task directly via ORM."""
    defaults = {
        "title": "Test Task",
        "status": "pending",
    }
    defaults.update(overrides)
    task = Task(**defaults)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _make_notification_orm(db, **overrides) -> NotificationQueue:
    """Create and persist a notification directly via ORM."""
    defaults = {
        "notification_type": "habit_nudge",
        "delivery_type": "notification",
        "status": "pending",
        "scheduled_at": datetime.now(tz=UTC),
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


def _make_checkin_orm(db, **overrides) -> StateCheckin:
    """Create and persist a state check-in directly via ORM."""
    defaults = {
        "checkin_type": "morning",
        "logged_at": datetime.now(tz=UTC),
    }
    defaults.update(overrides)
    checkin = StateCheckin(**defaults)
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


# ===========================================================================
# Happy path: consecutive_skips metric
# ===========================================================================


class TestConsecutiveSkipsMetric:
    """evaluate_rules fires for habits with consecutive skip responses."""

    def test_fires_when_skip_threshold_met(self, db):
        habit = _make_habit_orm(db, title="Meditation")
        rule = _make_rule(
            db,
            entity_type=RuleEntityType.habit,
            metric=RuleMetric.consecutive_skips,
            operator=RuleOperator.gte,
            threshold=3,
            notification_type="pattern_observation",
            message_template="You've skipped {entity_name} {metric_value} times",
        )

        # Create 3 consecutive skip responses
        base_time = datetime.now(tz=UTC) - timedelta(hours=10)
        for i in range(3):
            _make_notification_orm(
                db,
                target_entity_type="habit",
                target_entity_id=habit.id,
                notification_type="habit_nudge",
                status="responded",
                response="Skip today",
                responded_at=base_time + timedelta(hours=i),
                scheduled_by="system",
            )

        results = evaluate_rules(db)
        assert len(results) == 1
        assert results[0].fired is True
        assert results[0].reason == "fired"
        assert results[0].notifications_created == 1

        # Verify notification in queue
        notifs = db.query(NotificationQueue).filter(
            NotificationQueue.scheduled_by == "rule",
        ).all()
        assert len(notifs) == 1
        assert notifs[0].rule_id == rule.id
        assert "Meditation" in notifs[0].message
        assert "3" in notifs[0].message

    def test_does_not_fire_below_threshold(self, db):
        habit = _make_habit_orm(db, title="Meditation")
        _make_rule(
            db,
            metric=RuleMetric.consecutive_skips,
            threshold=3,
        )

        # Only 2 skips — below threshold
        base_time = datetime.now(tz=UTC) - timedelta(hours=5)
        for i in range(2):
            _make_notification_orm(
                db,
                target_entity_type="habit",
                target_entity_id=habit.id,
                notification_type="habit_nudge",
                status="responded",
                response="Skip today",
                responded_at=base_time + timedelta(hours=i),
                scheduled_by="system",
            )

        results = evaluate_rules(db)
        assert results[0].fired is False
        assert results[0].reason == "condition_not_met"

    def test_non_skip_response_breaks_chain(self, db):
        habit = _make_habit_orm(db, title="Meditation")
        _make_rule(
            db,
            metric=RuleMetric.consecutive_skips,
            threshold=3,
        )

        base_time = datetime.now(tz=UTC) - timedelta(hours=10)
        # Skip, then "Doing it now", then 2 more skips
        responses = ["Skip today", "Skip today", "Doing it now", "Skip today"]
        for i, resp in enumerate(responses):
            _make_notification_orm(
                db,
                target_entity_type="habit",
                target_entity_id=habit.id,
                notification_type="habit_nudge",
                status="responded",
                response=resp,
                responded_at=base_time + timedelta(hours=i),
                scheduled_by="system",
            )

        # Most recent 2 are skips, then "Doing it now" breaks chain → count = 2
        results = evaluate_rules(db)
        assert results[0].fired is False
        assert results[0].reason == "condition_not_met"


# ===========================================================================
# Happy path: non_responses metric
# ===========================================================================


class TestNonResponsesMetric:
    """evaluate_rules fires for habits with consecutive expired notifications."""

    def test_fires_when_non_response_threshold_met(self, db):
        habit = _make_habit_orm(db, title="Exercise")
        _make_rule(
            db,
            metric=RuleMetric.non_responses,
            operator=RuleOperator.gte,
            threshold=3,
            notification_type="pattern_observation",
            message_template="{entity_name} has {metric_value} non-responses",
        )

        base_time = datetime.now(tz=UTC) - timedelta(hours=10)
        for i in range(3):
            _make_notification_orm(
                db,
                target_entity_type="habit",
                target_entity_id=habit.id,
                status="expired",
                response=None,
                created_at=base_time + timedelta(hours=i),
                scheduled_by="system",
            )

        results = evaluate_rules(db)
        assert results[0].fired is True
        assert results[0].notifications_created == 1

    def test_responded_notification_breaks_chain(self, db):
        habit = _make_habit_orm(db, title="Exercise")
        _make_rule(
            db,
            metric=RuleMetric.non_responses,
            threshold=3,
        )

        base_time = datetime.now(tz=UTC) - timedelta(hours=10)
        # Responded, then 2 expired — only 2 consecutive non-responses
        _make_notification_orm(
            db,
            target_entity_type="habit",
            target_entity_id=habit.id,
            status="responded",
            response="Already done",
            responded_at=base_time,
            created_at=base_time,
            scheduled_by="system",
        )
        for i in range(1, 3):
            _make_notification_orm(
                db,
                target_entity_type="habit",
                target_entity_id=habit.id,
                status="expired",
                response=None,
                created_at=base_time + timedelta(hours=i),
                scheduled_by="system",
            )

        results = evaluate_rules(db)
        assert results[0].fired is False
        assert results[0].reason == "condition_not_met"


# ===========================================================================
# Happy path: days_untouched metric
# ===========================================================================


class TestDaysUntouchedMetric:
    """evaluate_rules fires for stale tasks."""

    def test_fires_for_stale_task(self, db):
        task = _make_task_orm(
            db,
            title="Clean garage",
            updated_at=datetime.now(tz=UTC) - timedelta(days=15),
        )
        _make_rule(
            db,
            entity_type=RuleEntityType.task,
            metric=RuleMetric.days_untouched,
            operator=RuleOperator.gte,
            threshold=14,
            notification_type="stale_work_nudge",
            message_template="{entity_name} hasn't been touched in {metric_value} days",
        )

        results = evaluate_rules(db)
        assert results[0].fired is True
        assert results[0].notifications_created == 1

        notifs = db.query(NotificationQueue).filter(
            NotificationQueue.scheduled_by == "rule",
        ).all()
        assert len(notifs) == 1
        assert "Clean garage" in notifs[0].message
        assert notifs[0].target_entity_type == "task"
        assert notifs[0].target_entity_id == task.id

    def test_does_not_fire_for_recent_task(self, db):
        _make_task_orm(
            db,
            title="Fresh task",
            updated_at=datetime.now(tz=UTC) - timedelta(days=5),
        )
        _make_rule(
            db,
            entity_type=RuleEntityType.task,
            metric=RuleMetric.days_untouched,
            threshold=14,
            notification_type="stale_work_nudge",
        )

        results = evaluate_rules(db)
        assert results[0].fired is False


# ===========================================================================
# Happy path: streak_length metric
# ===========================================================================


class TestStreakLengthMetric:
    """evaluate_rules fires when a habit streak is broken."""

    def test_fires_when_streak_broken(self, db):
        _make_habit_orm(
            db,
            title="Journaling",
            current_streak=0,
            best_streak=10,
        )
        _make_rule(
            db,
            metric=RuleMetric.streak_length,
            operator=RuleOperator.gte,
            threshold=7,
            notification_type="pattern_observation",
            message_template="Your {entity_name} streak of {metric_value} days ended",
        )

        results = evaluate_rules(db)
        assert results[0].fired is True
        assert results[0].notifications_created == 1

        notifs = db.query(NotificationQueue).filter(
            NotificationQueue.scheduled_by == "rule",
        ).all()
        assert "Journaling" in notifs[0].message
        assert "10" in notifs[0].message

    def test_does_not_fire_when_streak_ongoing(self, db):
        _make_habit_orm(
            db,
            title="Journaling",
            current_streak=5,
            best_streak=10,
        )
        _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
        )

        results = evaluate_rules(db)
        assert results[0].fired is False

    def test_does_not_fire_when_streak_below_threshold(self, db):
        _make_habit_orm(
            db,
            title="Journaling",
            current_streak=0,
            best_streak=3,
        )
        _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
        )

        results = evaluate_rules(db)
        assert results[0].fired is False


# ===========================================================================
# Cooldown enforcement
# ===========================================================================


class TestCooldown:
    """Cooldown prevents re-firing within the cooldown window."""

    def test_rule_in_cooldown_is_skipped(self, db):
        _make_habit_orm(db, current_streak=0, best_streak=10)
        _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            cooldown_hours=24,
            last_triggered_at=datetime.now(tz=UTC) - timedelta(hours=2),
        )

        results = evaluate_rules(db)
        assert results[0].fired is False
        assert results[0].reason == "cooldown"

    def test_rule_after_cooldown_fires(self, db):
        _make_habit_orm(db, current_streak=0, best_streak=10)
        _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            cooldown_hours=24,
            last_triggered_at=datetime.now(tz=UTC) - timedelta(hours=25),
        )

        results = evaluate_rules(db)
        assert results[0].fired is True

    def test_fire_then_cooldown_then_fire(self, db):
        _make_habit_orm(db, current_streak=0, best_streak=10)
        _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            cooldown_hours=24,
        )

        # First evaluation — fires
        results1 = evaluate_rules(db)
        assert results1[0].fired is True

        # Second evaluation — cooldown blocks
        results2 = evaluate_rules(db)
        assert results2[0].fired is False
        assert results2[0].reason == "cooldown"

    def test_respect_cooldown_false_bypasses_cooldown(self, db):
        _make_habit_orm(db, current_streak=0, best_streak=10)
        rule = _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            cooldown_hours=24,
            last_triggered_at=datetime.now(tz=UTC) - timedelta(hours=2),
        )

        results = evaluate_rules(db, rule_id=rule.id, respect_cooldown=False)
        assert results[0].fired is True


# ===========================================================================
# Entity-scoped vs global rules
# ===========================================================================


class TestEntityScoping:
    """Entity-scoped rules evaluate only the target entity; global rules evaluate all."""

    def test_scoped_rule_evaluates_only_target(self, db):
        habit_x = _make_habit_orm(db, title="Habit X", current_streak=0, best_streak=10)
        _make_habit_orm(db, title="Habit Y", current_streak=0, best_streak=10)
        _make_habit_orm(db, title="Habit Z", current_streak=0, best_streak=10)

        _make_rule(
            db,
            entity_id=habit_x.id,
            metric=RuleMetric.streak_length,
            threshold=7,
            notification_type="pattern_observation",
        )

        results = evaluate_rules(db)
        assert results[0].fired is True
        assert results[0].notifications_created == 1

        notifs = db.query(NotificationQueue).filter(
            NotificationQueue.scheduled_by == "rule",
        ).all()
        assert len(notifs) == 1
        assert notifs[0].target_entity_id == habit_x.id

    def test_global_rule_evaluates_all_matching(self, db):
        _make_habit_orm(db, title="Habit X", current_streak=0, best_streak=10)
        _make_habit_orm(db, title="Habit Y", current_streak=0, best_streak=10)
        _make_habit_orm(db, title="Habit Z", current_streak=0, best_streak=10)

        _make_rule(
            db,
            entity_id=None,
            metric=RuleMetric.streak_length,
            threshold=7,
            notification_type="pattern_observation",
        )

        results = evaluate_rules(db)
        assert results[0].fired is True
        assert results[0].notifications_created == 3
        assert results[0].entities_evaluated == 3


# ===========================================================================
# Template rendering
# ===========================================================================


class TestTemplateRendering:
    """Message templates resolve all 5 placeholders correctly."""

    def test_all_placeholders_resolve(self, db):
        _make_habit_orm(db, title="Meditation", current_streak=0, best_streak=10)
        _make_rule(
            db,
            name="Streak break notice",
            metric=RuleMetric.streak_length,
            threshold=7,
            notification_type="pattern_observation",
            message_template=(
                "{rule_name}: {entity_type} '{entity_name}' hit "
                "{metric_value} (threshold {threshold})"
            ),
        )

        evaluate_rules(db)

        notifs = db.query(NotificationQueue).filter(
            NotificationQueue.scheduled_by == "rule",
        ).all()
        assert len(notifs) == 1
        msg = notifs[0].message
        assert "Streak break notice" in msg
        assert "habit" in msg
        assert "Meditation" in msg
        assert "10" in msg
        assert "7" in msg


# ===========================================================================
# Error resilience
# ===========================================================================


class TestErrorResilience:
    """Evaluation completes gracefully when entities are missing or broken."""

    def test_deleted_entity_skipped_gracefully(self, db):
        habit = _make_habit_orm(db, title="Ghost Habit", current_streak=0, best_streak=10)
        _make_rule(
            db,
            entity_id=habit.id,
            metric=RuleMetric.streak_length,
            threshold=7,
        )

        # Delete the habit before evaluation
        db.delete(habit)
        db.commit()

        results = evaluate_rules(db)
        assert results[0].fired is False
        assert results[0].reason == "no_matching_entities"

    def test_disabled_rule_not_evaluated(self, db):
        _make_habit_orm(db, current_streak=0, best_streak=10)
        _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            enabled=False,
        )

        results = evaluate_rules(db)
        assert len(results) == 0


# ===========================================================================
# Friction matching (stale task nudge)
# ===========================================================================


class TestFrictionMatching:
    """Stale task nudge respects friction vs. current energy."""

    def test_fires_when_friction_within_energy(self, db):
        _make_task_orm(
            db,
            title="Easy task",
            activation_friction=2,
            updated_at=datetime.now(tz=UTC) - timedelta(days=15),
        )
        _make_checkin_orm(db, energy_level=3, logged_at=datetime.now(tz=UTC))
        _make_rule(
            db,
            entity_type=RuleEntityType.task,
            metric=RuleMetric.days_untouched,
            threshold=14,
            notification_type="stale_work_nudge",
        )

        results = evaluate_rules(db)
        assert results[0].fired is True

    def test_skips_when_friction_exceeds_energy(self, db):
        _make_task_orm(
            db,
            title="Hard task",
            activation_friction=4,
            updated_at=datetime.now(tz=UTC) - timedelta(days=15),
        )
        _make_checkin_orm(db, energy_level=1, logged_at=datetime.now(tz=UTC))
        _make_rule(
            db,
            entity_type=RuleEntityType.task,
            metric=RuleMetric.days_untouched,
            threshold=14,
            notification_type="stale_work_nudge",
        )

        results = evaluate_rules(db)
        assert results[0].fired is False
        assert results[0].reason == "condition_not_met"

    def test_fires_without_checkin_data(self, db):
        """No recent check-in → friction filter skipped, evaluates on days_untouched alone."""
        _make_task_orm(
            db,
            title="Hard task",
            activation_friction=5,
            updated_at=datetime.now(tz=UTC) - timedelta(days=15),
        )
        # No check-in created — friction filter should be skipped
        _make_rule(
            db,
            entity_type=RuleEntityType.task,
            metric=RuleMetric.days_untouched,
            threshold=14,
            notification_type="stale_work_nudge",
        )

        results = evaluate_rules(db)
        assert results[0].fired is True

    def test_old_checkin_ignored(self, db):
        """Check-in older than 24h is treated as no check-in (friction filter skipped)."""
        _make_task_orm(
            db,
            title="Hard task",
            activation_friction=5,
            updated_at=datetime.now(tz=UTC) - timedelta(days=15),
        )
        _make_checkin_orm(
            db,
            energy_level=1,
            logged_at=datetime.now(tz=UTC) - timedelta(hours=25),
        )
        _make_rule(
            db,
            entity_type=RuleEntityType.task,
            metric=RuleMetric.days_untouched,
            threshold=14,
            notification_type="stale_work_nudge",
        )

        results = evaluate_rules(db)
        assert results[0].fired is True


# ===========================================================================
# Notification properties
# ===========================================================================


class TestNotificationProperties:
    """Notifications created by evaluation have correct scheduled_by and rule_id."""

    def test_notification_has_rule_metadata(self, db):
        habit = _make_habit_orm(db, title="Test", current_streak=0, best_streak=10)
        rule = _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            notification_type="pattern_observation",
        )

        evaluate_rules(db)

        notifs = db.query(NotificationQueue).filter(
            NotificationQueue.scheduled_by == "rule",
        ).all()
        assert len(notifs) == 1
        assert notifs[0].scheduled_by == "rule"
        assert notifs[0].rule_id == rule.id
        assert notifs[0].status == "pending"
        assert notifs[0].delivery_type == "notification"
        assert notifs[0].target_entity_type == "habit"
        assert notifs[0].target_entity_id == habit.id

    def test_notification_gets_default_canned_responses(self, db):
        _make_habit_orm(db, current_streak=0, best_streak=10)
        _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            notification_type="pattern_observation",
        )

        evaluate_rules(db)

        notifs = db.query(NotificationQueue).filter(
            NotificationQueue.scheduled_by == "rule",
        ).all()
        assert notifs[0].canned_responses is not None
        assert "Noted" in notifs[0].canned_responses

    def test_last_triggered_at_updated_on_fire(self, db):
        _make_habit_orm(db, current_streak=0, best_streak=10)
        rule = _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
        )
        assert rule.last_triggered_at is None

        evaluate_rules(db)

        db.refresh(rule)
        assert rule.last_triggered_at is not None

    def test_idempotent_within_cooldown(self, db):
        """Running evaluation twice within cooldown produces no duplicates."""
        _make_habit_orm(db, current_streak=0, best_streak=10)
        _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            cooldown_hours=24,
        )

        evaluate_rules(db)
        evaluate_rules(db)

        notifs = db.query(NotificationQueue).filter(
            NotificationQueue.scheduled_by == "rule",
        ).all()
        assert len(notifs) == 1


# ===========================================================================
# API endpoint tests
# ===========================================================================


class TestEvaluateAllEndpoint:
    """POST /api/rules/evaluate"""

    def test_evaluate_all_returns_results(self, client, db):
        _make_habit_orm(db, current_streak=0, best_streak=10)
        _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            notification_type="pattern_observation",
        )

        resp = client.post(f"{RULES_URL}/evaluate")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["fired"] is True
        assert data[0]["reason"] == "fired"
        assert data[0]["notifications_created"] == 1

    def test_evaluate_all_empty_when_no_rules(self, client):
        resp = client.post(f"{RULES_URL}/evaluate")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_evaluate_all_skips_disabled_rules(self, client, db):
        _make_habit_orm(db, current_streak=0, best_streak=10)
        _make_rule(db, metric=RuleMetric.streak_length, threshold=7, enabled=False)

        resp = client.post(f"{RULES_URL}/evaluate")
        assert resp.status_code == 200
        assert resp.json() == []


class TestEvaluateSingleEndpoint:
    """POST /api/rules/{rule_id}/evaluate"""

    def test_evaluate_single_rule(self, client, db):
        _make_habit_orm(db, current_streak=0, best_streak=10)
        rule = _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            notification_type="pattern_observation",
        )

        resp = client.post(f"{RULES_URL}/{rule.id}/evaluate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fired"] is True
        assert data["rule_id"] == str(rule.id)

    def test_evaluate_single_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"{RULES_URL}/{fake_id}/evaluate")
        assert resp.status_code == 404

    def test_evaluate_single_bypass_cooldown(self, client, db):
        _make_habit_orm(db, current_streak=0, best_streak=10)
        rule = _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            cooldown_hours=24,
            last_triggered_at=datetime.now(tz=UTC) - timedelta(hours=2),
        )

        # With cooldown respected (default) — should be skipped
        resp = client.post(f"{RULES_URL}/{rule.id}/evaluate")
        assert resp.json()["fired"] is False
        assert resp.json()["reason"] == "cooldown"

        # With cooldown bypassed
        resp = client.post(
            f"{RULES_URL}/{rule.id}/evaluate",
            params={"respect_cooldown": False},
        )
        assert resp.json()["fired"] is True

    def test_evaluate_single_evaluates_disabled_rule(self, client, db):
        """Single-rule evaluate works even if the rule is disabled."""
        _make_habit_orm(db, current_streak=0, best_streak=10)
        rule = _make_rule(
            db,
            metric=RuleMetric.streak_length,
            threshold=7,
            enabled=False,
        )

        resp = client.post(f"{RULES_URL}/{rule.id}/evaluate")
        assert resp.status_code == 200
        assert resp.json()["fired"] is True


# ===========================================================================
# No matching entities
# ===========================================================================


class TestNoMatchingEntities:
    """Rules report no_matching_entities when no relevant entities exist."""

    def test_habit_rule_with_no_habits(self, db):
        _make_rule(db, metric=RuleMetric.consecutive_skips, threshold=3)

        results = evaluate_rules(db)
        assert results[0].fired is False
        assert results[0].reason == "no_matching_entities"

    def test_task_rule_with_no_tasks(self, db):
        _make_rule(
            db,
            entity_type=RuleEntityType.task,
            metric=RuleMetric.days_untouched,
            threshold=14,
            notification_type="stale_work_nudge",
        )

        results = evaluate_rules(db)
        assert results[0].fired is False
        assert results[0].reason == "no_matching_entities"

    def test_task_rule_ignores_completed_tasks(self, db):
        _make_task_orm(
            db,
            title="Done task",
            status="completed",
            updated_at=datetime.now(tz=UTC) - timedelta(days=30),
        )
        _make_rule(
            db,
            entity_type=RuleEntityType.task,
            metric=RuleMetric.days_untouched,
            threshold=14,
            notification_type="stale_work_nudge",
        )

        results = evaluate_rules(db)
        assert results[0].fired is False
        assert results[0].reason == "no_matching_entities"
