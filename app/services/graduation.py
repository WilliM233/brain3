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

"""Graduation evaluation, execution, and frequency step-down service for habit scaffolding."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import ActivityLog, Habit, NotificationQueue
from app.services.graduation_defaults import resolve_graduation_params


class GraduationResult(BaseModel):
    """Result of evaluating a habit's graduation eligibility."""

    eligible: bool
    habit_id: UUID
    current_rate: float
    total_notifications: int
    already_done_count: int
    window_days: int
    target_rate: float
    days_since_introduction: int
    threshold_days: int
    meets_rate: bool
    meets_threshold: bool
    blocking_reasons: list[str]


class GraduationExecutionResult(BaseModel):
    """Result of executing a habit graduation."""

    success: bool
    habit_id: UUID
    previous_scaffolding_status: str
    previous_notification_frequency: str
    evaluation: GraduationResult | None
    message: str


def apply_re_scaffold_tightening(
    window: int, target: float, threshold: int, re_scaffold_count: int,
) -> tuple[int, float, int]:
    """Tighten graduation criteria based on re-scaffold history."""
    for _ in range(re_scaffold_count):
        window = int(window * 1.25)
        target = min(target + 0.05, 0.95)
        threshold = int(threshold * 1.25)
    return (window, target, threshold)


def evaluate_graduation(
    db: Session,
    habit_id: UUID,
) -> GraduationResult:
    """Evaluate whether a habit is eligible for graduation.

    This function does NOT change state — it returns a result.
    State transitions happen in [2G-02].
    """
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if habit is None:
        raise ValueError(f"Habit {habit_id} not found")

    # Gate: only accountable habits can be evaluated
    if habit.scaffolding_status != "accountable":
        return GraduationResult(
            eligible=False,
            habit_id=habit_id,
            current_rate=0.0,
            total_notifications=0,
            already_done_count=0,
            window_days=0,
            target_rate=0.0,
            days_since_introduction=0,
            threshold_days=0,
            meets_rate=False,
            meets_threshold=False,
            blocking_reasons=[
                "Habit scaffolding_status must be 'accountable' to evaluate graduation"
            ],
        )

    # Resolve parameters with friction-aware defaults
    window, target, threshold = resolve_graduation_params(habit)

    # Apply re-scaffold tightening if applicable
    if habit.re_scaffold_count > 0:
        window, target, threshold = apply_re_scaffold_tightening(
            window, target, threshold, habit.re_scaffold_count,
        )

    now = datetime.now(tz=UTC)

    # Compute days since introduction
    if habit.introduced_at is not None:
        days_since_introduction = (now.date() - habit.introduced_at).days
    else:
        days_since_introduction = 0

    meets_threshold = days_since_introduction >= threshold

    # Query notification responses in the rolling window
    window_start = now - timedelta(days=window)
    notifications = (
        db.query(NotificationQueue)
        .filter(
            NotificationQueue.target_entity_type == "habit",
            NotificationQueue.target_entity_id == habit_id,
            NotificationQueue.notification_type == "habit_nudge",
            NotificationQueue.scheduled_at >= window_start,
            NotificationQueue.status.in_(["responded", "expired"]),
        )
        .all()
    )

    total_notifications = len(notifications)

    # Handle zero-notification edge case
    if total_notifications == 0:
        return GraduationResult(
            eligible=False,
            habit_id=habit_id,
            current_rate=0.0,
            total_notifications=0,
            already_done_count=0,
            window_days=window,
            target_rate=target,
            days_since_introduction=days_since_introduction,
            threshold_days=threshold,
            meets_rate=False,
            meets_threshold=meets_threshold,
            blocking_reasons=["No notification data in evaluation window"],
        )

    already_done_count = sum(
        1 for n in notifications if n.response == "Already done"
    )
    current_rate = already_done_count / total_notifications

    meets_rate = current_rate >= target

    # Build blocking reasons
    blocking_reasons: list[str] = []
    if not meets_rate:
        blocking_reasons.append(
            f"Rate {current_rate:.0%} below target {target:.0%}"
        )
    if not meets_threshold:
        blocking_reasons.append(
            f"{days_since_introduction} days since introduction, need {threshold}"
        )

    eligible = meets_rate and meets_threshold

    return GraduationResult(
        eligible=eligible,
        habit_id=habit_id,
        current_rate=current_rate,
        total_notifications=total_notifications,
        already_done_count=already_done_count,
        window_days=window,
        target_rate=target,
        days_since_introduction=days_since_introduction,
        threshold_days=threshold,
        meets_rate=meets_rate,
        meets_threshold=meets_threshold,
        blocking_reasons=blocking_reasons,
    )


def graduate_habit(
    db: Session,
    habit_id: UUID,
    force: bool = False,
) -> GraduationExecutionResult:
    """Execute the graduation state transition for a habit.

    Moves scaffolding_status from 'accountable' to 'graduated' and sets
    notification_frequency to 'graduated'. Does NOT change habit.status —
    the habit remains active and continues appearing in routine checklists.
    """
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    # Snapshot previous values for audit trail
    previous_scaffolding = habit.scaffolding_status
    previous_frequency = habit.notification_frequency

    # Already graduated — idempotency guard
    if habit.scaffolding_status == "graduated":
        return GraduationExecutionResult(
            success=False,
            habit_id=habit_id,
            previous_scaffolding_status=previous_scaffolding,
            previous_notification_frequency=previous_frequency,
            evaluation=None,
            message="Habit is already graduated",
        )

    # Status must be active
    if habit.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot graduate a habit with status '{habit.status}' — must be 'active'",
        )

    # Scaffolding must be accountable
    if habit.scaffolding_status != "accountable":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot graduate from scaffolding_status '{habit.scaffolding_status}' "
                "— must be 'accountable'"
            ),
        )

    # Evaluate eligibility
    evaluation = evaluate_graduation(db, habit_id)

    if not force and not evaluation.eligible:
        return GraduationExecutionResult(
            success=False,
            habit_id=habit_id,
            previous_scaffolding_status=previous_scaffolding,
            previous_notification_frequency=previous_frequency,
            evaluation=evaluation,
            message=(
                "Habit does not meet graduation criteria. "
                + "; ".join(evaluation.blocking_reasons)
            ),
        )

    # Execute transition
    habit.scaffolding_status = "graduated"
    habit.notification_frequency = "graduated"

    # Log activity entry
    forced_label = " (forced)" if force else ""
    activity = ActivityLog(
        action_type="completed",
        notes=(
            f"Habit graduated{forced_label}: {habit.title}. "
            f"Rate: {evaluation.current_rate:.0%} over {evaluation.window_days} days. "
            f"Streak preserved at {habit.best_streak}."
        ),
        habit_id=habit_id,
    )
    db.add(activity)

    # Atomic commit — transition + activity log in one transaction
    db.commit()
    db.refresh(habit)

    return GraduationExecutionResult(
        success=True,
        habit_id=habit_id,
        previous_scaffolding_status=previous_scaffolding,
        previous_notification_frequency=previous_frequency,
        evaluation=evaluation,
        message=f"Habit '{habit.title}' graduated successfully{forced_label}",
    )


# ===========================================================================
# [2G-03] Frequency Step-Down
# ===========================================================================

# Step-down progression — terminal states (graduated, none) are excluded.
FREQUENCY_ORDER = [
    "daily",
    "every_other_day",
    "twice_week",
    "weekly",
]

# Evaluation constants — kept as module-level for easy adjustment.
STEP_DOWN_NOTIFICATION_LIMIT = 14
STEP_DOWN_MIN_NOTIFICATIONS = 5
STEP_DOWN_RATE_THRESHOLD = 0.60
STEP_DOWN_COOLDOWN_DAYS = 7


def next_step_down(current: str) -> str | None:
    """Return the next lower frequency, or None if already at weekly."""
    try:
        idx = FREQUENCY_ORDER.index(current)
        if idx + 1 < len(FREQUENCY_ORDER):
            return FREQUENCY_ORDER[idx + 1]
    except ValueError:
        pass
    return None


class FrequencyStepResult(BaseModel):
    """Result of evaluating a habit's frequency step-down eligibility."""

    recommend_step_down: bool
    habit_id: UUID
    current_frequency: str
    recommended_frequency: str | None
    current_rate: float
    notifications_evaluated: int
    cooldown_active: bool
    cooldown_expires_at: datetime | None
    blocking_reasons: list[str]


class FrequencyChangeResult(BaseModel):
    """Result of applying a frequency step-down."""

    success: bool
    habit_id: UUID
    previous_frequency: str
    new_frequency: str
    message: str


def evaluate_frequency_step_down(
    db: Session,
    habit_id: UUID,
) -> FrequencyStepResult:
    """Evaluate whether a habit should step down to a lower notification frequency.

    Uses the N most recent notifications (LIMIT-based, not date-based) and a
    60% "already done" threshold. Respects a 7-day cooldown after any frequency change.
    """
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if habit is None:
        raise ValueError(f"Habit {habit_id} not found")

    now = datetime.now(tz=UTC)

    # Helper to build a no-recommendation result
    def _no_recommendation(
        *,
        reasons: list[str],
        rate: float = 0.0,
        evaluated: int = 0,
        cooldown: bool = False,
        cooldown_expires: datetime | None = None,
    ) -> FrequencyStepResult:
        return FrequencyStepResult(
            recommend_step_down=False,
            habit_id=habit_id,
            current_frequency=habit.notification_frequency,
            recommended_frequency=None,
            current_rate=rate,
            notifications_evaluated=evaluated,
            cooldown_active=cooldown,
            cooldown_expires_at=cooldown_expires,
            blocking_reasons=reasons,
        )

    # Gate: must be active + accountable
    if habit.status != "active" or habit.scaffolding_status != "accountable":
        return _no_recommendation(
            reasons=["Habit must be active with scaffolding_status 'accountable'"],
        )

    # Gate: current frequency must be in the step-down progression
    if habit.notification_frequency not in FREQUENCY_ORDER:
        return _no_recommendation(
            reasons=[
                f"Frequency '{habit.notification_frequency}' is not in the "
                "step-down progression"
            ],
        )

    # Cooldown check
    if habit.last_frequency_changed_at is not None:
        last_changed = habit.last_frequency_changed_at
        # SQLite returns naive datetimes — normalize to UTC-aware for comparison
        if last_changed.tzinfo is None:
            last_changed = last_changed.replace(tzinfo=UTC)
        cooldown_expires = last_changed + timedelta(
            days=STEP_DOWN_COOLDOWN_DAYS,
        )
        if now < cooldown_expires:
            return _no_recommendation(
                cooldown=True,
                cooldown_expires=cooldown_expires,
                reasons=[
                    f"Cooldown active — last frequency change was "
                    f"{(now - last_changed).days} days ago, "
                    f"need {STEP_DOWN_COOLDOWN_DAYS}"
                ],
            )

    # Query most recent N notifications
    notifications = (
        db.query(NotificationQueue)
        .filter(
            NotificationQueue.target_entity_type == "habit",
            NotificationQueue.target_entity_id == habit_id,
            NotificationQueue.notification_type == "habit_nudge",
            NotificationQueue.status.in_(["responded", "expired"]),
        )
        .order_by(NotificationQueue.scheduled_at.desc())
        .limit(STEP_DOWN_NOTIFICATION_LIMIT)
        .all()
    )

    total = len(notifications)

    # Minimum data check
    if total < STEP_DOWN_MIN_NOTIFICATIONS:
        return _no_recommendation(
            evaluated=total,
            reasons=[
                f"Need at least {STEP_DOWN_MIN_NOTIFICATIONS} notifications "
                f"to evaluate step-down (have {total})"
            ],
        )

    # Compute "already done" rate
    already_done_count = sum(
        1 for n in notifications if n.response == "Already done"
    )
    rate = already_done_count / total

    # Check if already at minimum stepped frequency
    recommended = next_step_down(habit.notification_frequency)
    if recommended is None:
        return _no_recommendation(
            rate=rate,
            evaluated=total,
            reasons=[
                "Already at minimum stepped frequency (weekly). "
                "Full graduation evaluated separately."
            ],
        )

    # Threshold check
    if rate < STEP_DOWN_RATE_THRESHOLD:
        return _no_recommendation(
            rate=rate,
            evaluated=total,
            reasons=[
                f"Rate {rate:.0%} below step-down threshold "
                f"{STEP_DOWN_RATE_THRESHOLD:.0%}"
            ],
        )

    return FrequencyStepResult(
        recommend_step_down=True,
        habit_id=habit_id,
        current_frequency=habit.notification_frequency,
        recommended_frequency=recommended,
        current_rate=rate,
        notifications_evaluated=total,
        cooldown_active=False,
        cooldown_expires_at=None,
        blocking_reasons=[],
    )


def apply_frequency_step_down(
    db: Session,
    habit_id: UUID,
    new_frequency: str,
) -> FrequencyChangeResult:
    """Apply a one-level frequency step-down to a habit.

    Validates that new_frequency is exactly one step below the current frequency.
    Rejects skipping levels, going backwards, or invalid frequencies.
    """
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    previous = habit.notification_frequency

    # Validate: new_frequency must be exactly one step below current
    expected_next = next_step_down(previous)
    if expected_next is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot step down from '{previous}' — "
                "not in the step-down progression or already at minimum"
            ),
        )
    if new_frequency != expected_next:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid step-down: '{previous}' → '{new_frequency}'. "
                f"Expected exactly one level: '{previous}' → '{expected_next}'"
            ),
        )

    # Apply the change
    habit.notification_frequency = new_frequency
    habit.last_frequency_changed_at = datetime.now(tz=UTC)

    # Log activity
    activity = ActivityLog(
        action_type="completed",
        notes=(
            f"Notification frequency stepped down: {habit.title}. "
            f"{previous} → {new_frequency}."
        ),
        habit_id=habit_id,
    )
    db.add(activity)
    db.commit()
    db.refresh(habit)

    return FrequencyChangeResult(
        success=True,
        habit_id=habit_id,
        previous_frequency=previous,
        new_frequency=new_frequency,
        message=(
            f"Frequency stepped down for '{habit.title}': "
            f"{previous} → {new_frequency}"
        ),
    )
