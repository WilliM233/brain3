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

"""Rule evaluation engine — checks rules against BRAIN data and creates notifications."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Habit, NotificationQueue, Rule, StateCheckin, Task
from app.schemas.rule import RuleEntityType, RuleMetric, RuleOperator
from app.services.notification_defaults import get_default_responses

logger = logging.getLogger(__name__)


@dataclass
class RuleEvaluationResult:
    """Summary of a single rule's evaluation."""

    rule_id: UUID
    rule_name: str
    fired: bool
    reason: str  # "fired", "cooldown", "condition_not_met", "no_matching_entities", "error"
    notifications_created: int = 0
    entities_evaluated: int = 0


def evaluate_rules(
    db: Session,
    rule_id: UUID | None = None,
    respect_cooldown: bool = True,
) -> list[RuleEvaluationResult]:
    """Evaluate all enabled rules (or a single rule if rule_id is provided).

    Creates notifications for rules whose conditions are met and cooldown has elapsed.
    Returns a summary of evaluation results.
    """
    if rule_id is not None:
        rules = db.query(Rule).filter(Rule.id == rule_id).all()
    else:
        rules = db.query(Rule).filter(Rule.enabled.is_(True)).all()

    now = datetime.now(tz=UTC)
    results = []

    for rule in rules:
        result = _evaluate_single_rule(db, rule, now, respect_cooldown)
        results.append(result)

    return results


def _evaluate_single_rule(
    db: Session,
    rule: Rule,
    now: datetime,
    respect_cooldown: bool,
) -> RuleEvaluationResult:
    """Evaluate a single rule against current data."""
    # Check cooldown
    if respect_cooldown and rule.last_triggered_at is not None:
        triggered = rule.last_triggered_at
        if triggered.tzinfo is None:
            triggered = triggered.replace(tzinfo=UTC)
        cooldown_expiry = triggered + timedelta(hours=rule.cooldown_hours)
        if now < cooldown_expiry:
            return RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                fired=False,
                reason="cooldown",
            )

    try:
        entities = _get_entities(db, rule)
    except Exception as exc:
        logger.warning("Error fetching entities for rule %s: %s", rule.name, exc)
        return RuleEvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            fired=False,
            reason="error",
        )

    if not entities:
        return RuleEvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            fired=False,
            reason="no_matching_entities",
        )

    notifications_created = 0
    entities_evaluated = len(entities)

    # For friction matching on stale tasks, get recent energy
    recent_energy = None
    if rule.metric == RuleMetric.days_untouched:
        recent_energy = _get_recent_energy(db, now)

    for entity in entities:
        try:
            metric_value = _compute_metric(db, rule, entity, now)
        except Exception as exc:
            logger.warning(
                "Error computing metric for rule '%s', entity %s: %s",
                rule.name, entity.id, exc,
            )
            continue

        # Friction matching for stale task nudge: skip if task friction > current energy
        if rule.metric == RuleMetric.days_untouched and recent_energy is not None:
            friction = getattr(entity, "activation_friction", None)
            if friction is not None and friction > recent_energy:
                continue

        if _compare(metric_value, rule.operator, rule.threshold):
            try:
                _create_notification(db, rule, entity, metric_value, now)
                notifications_created += 1
            except Exception as exc:
                logger.warning(
                    "Error creating notification for rule '%s', entity %s: %s",
                    rule.name, entity.id, exc,
                )
                continue

    if notifications_created > 0:
        rule.last_triggered_at = now
        db.commit()
        return RuleEvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            fired=True,
            reason="fired",
            notifications_created=notifications_created,
            entities_evaluated=entities_evaluated,
        )

    return RuleEvaluationResult(
        rule_id=rule.id,
        rule_name=rule.name,
        fired=False,
        reason="condition_not_met",
        entities_evaluated=entities_evaluated,
    )


# ---------------------------------------------------------------------------
# Entity fetching
# ---------------------------------------------------------------------------


def _get_entities(db: Session, rule: Rule) -> list:
    """Fetch the entities a rule should evaluate."""
    entity_type = rule.entity_type

    if entity_type == RuleEntityType.habit:
        query = db.query(Habit).filter(Habit.status == "active")
        if rule.entity_id is not None:
            query = query.filter(Habit.id == rule.entity_id)
        return query.all()

    if entity_type == RuleEntityType.task:
        query = db.query(Task).filter(Task.status.in_(["pending", "active"]))
        if rule.entity_id is not None:
            query = query.filter(Task.id == rule.entity_id)
        return query.all()

    return []


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def _compute_metric(
    db: Session, rule: Rule, entity: Habit | Task, now: datetime,
) -> int:
    """Compute the metric value for a rule against a specific entity."""
    metric = rule.metric

    if metric == RuleMetric.consecutive_skips:
        return _compute_consecutive_skips(db, entity)

    if metric == RuleMetric.non_responses:
        return _compute_non_responses(db, entity)

    if metric == RuleMetric.days_untouched:
        return _compute_days_untouched(entity, now)

    if metric == RuleMetric.streak_length:
        return _compute_streak_length(entity)

    return 0


def _compute_consecutive_skips(db: Session, habit: Habit) -> int:
    """Count consecutive 'Skip today' responses on habit nudge notifications.

    Reads backward from the most recent responded notification. Stops at the
    first non-skip response.
    """
    notifications = (
        db.query(NotificationQueue)
        .filter(
            NotificationQueue.target_entity_type == "habit",
            NotificationQueue.target_entity_id == habit.id,
            NotificationQueue.notification_type == "habit_nudge",
            NotificationQueue.status == "responded",
        )
        .order_by(NotificationQueue.responded_at.desc())
        .all()
    )

    count = 0
    for nq in notifications:
        if nq.response == "Skip today":
            count += 1
        else:
            break
    return count


def _compute_non_responses(db: Session, habit: Habit) -> int:
    """Count consecutive expired notifications with no response.

    Reads backward from the most recent notification. Stops at the first
    notification that has a response (any status).
    """
    notifications = (
        db.query(NotificationQueue)
        .filter(
            NotificationQueue.target_entity_type == "habit",
            NotificationQueue.target_entity_id == habit.id,
        )
        .order_by(NotificationQueue.created_at.desc())
        .all()
    )

    count = 0
    for nq in notifications:
        if nq.status == "expired" and nq.response is None:
            count += 1
        else:
            break
    return count


def _compute_days_untouched(task: Task, now: datetime) -> int:
    """Compute days since a task was last updated."""
    if task.updated_at is None:
        return 0
    updated = task.updated_at
    if updated.tzinfo is None:
        delta = now.replace(tzinfo=None) - updated
    else:
        delta = now - updated
    return delta.days


def _compute_streak_length(habit: Habit) -> int:
    """Compute the broken streak length for a habit.

    Returns best_streak when current_streak is 0, indicating a recently broken
    streak. Returns 0 when the streak is ongoing (no break to report).
    """
    if habit.current_streak == 0 and habit.best_streak > 0:
        return habit.best_streak
    return 0


# ---------------------------------------------------------------------------
# Comparison and helpers
# ---------------------------------------------------------------------------


def _compare(value: int, operator: RuleOperator, threshold: int) -> bool:
    """Apply a comparison operator."""
    if operator == RuleOperator.gte:
        return value >= threshold
    if operator == RuleOperator.lte:
        return value <= threshold
    if operator == RuleOperator.eq:
        return value == threshold
    return False


def _get_recent_energy(db: Session, now: datetime) -> int | None:
    """Get the most recent check-in energy level within the last 24 hours."""
    cutoff = now - timedelta(hours=24)
    checkin = (
        db.query(StateCheckin)
        .filter(
            StateCheckin.logged_at >= cutoff,
            StateCheckin.energy_level.isnot(None),
        )
        .order_by(StateCheckin.logged_at.desc())
        .first()
    )
    if checkin is not None:
        return checkin.energy_level
    return None


# ---------------------------------------------------------------------------
# Notification creation
# ---------------------------------------------------------------------------


def _create_notification(
    db: Session,
    rule: Rule,
    entity: Habit | Task,
    metric_value: int,
    now: datetime,
) -> NotificationQueue:
    """Create a notification in the queue for a fired rule."""
    entity_name = (
        getattr(entity, "title", None)
        or getattr(entity, "name", None)
        or "Unknown"
    )
    entity_type_str = rule.entity_type.value

    template_vars = {
        "entity_name": entity_name,
        "entity_type": entity_type_str,
        "metric_value": metric_value,
        "threshold": rule.threshold,
        "rule_name": rule.name,
    }

    try:
        message = rule.message_template.format_map(template_vars)
    except (KeyError, ValueError) as exc:
        logger.warning(
            "Template rendering failed for rule '%s': %s", rule.name, exc,
        )
        raise

    canned_responses = get_default_responses(rule.notification_type)

    # scheduled_date is the calendar-day anchor used by the companion
    # app's recent view (Stream C E5). Derived from now.date() — server
    # TZ in BRAIN runs UTC, so this is the UTC date of `now`. A future
    # SERVER_TZ setting ([2C-04]) will replace this default if BRAIN
    # ever runs in a non-UTC tz.
    notification = NotificationQueue(
        notification_type=rule.notification_type,
        delivery_type="notification",
        status="pending",
        scheduled_at=now,
        scheduled_date=now.date(),
        target_entity_type=entity_type_str,
        target_entity_id=entity.id,
        message=message,
        canned_responses=canned_responses,
        scheduled_by="rule",
        rule_id=rule.id,
    )
    db.add(notification)
    db.flush()
    return notification
