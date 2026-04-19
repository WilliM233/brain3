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

"""Graduation evaluation, execution, frequency step-down,
re-scaffolding, and stacking recommendation service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models import ActivityLog, Habit, HabitCompletion, NotificationQueue, Routine
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
    days_accountable: int
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
    window: int,
    target: float,
    threshold: int,
    re_scaffold_count: int,
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

    # Gate: habit must be active
    if habit.status != "active":
        return GraduationResult(
            eligible=False,
            habit_id=habit_id,
            current_rate=0.0,
            total_notifications=0,
            already_done_count=0,
            window_days=0,
            target_rate=0.0,
            days_accountable=0,
            threshold_days=0,
            meets_rate=False,
            meets_threshold=False,
            blocking_reasons=[
                f"Habit status must be 'active' to evaluate graduation (current: {habit.status})"
            ],
        )

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
            days_accountable=0,
            threshold_days=0,
            meets_rate=False,
            meets_threshold=False,
            blocking_reasons=[
                "Habit scaffolding_status must be 'accountable' to evaluate "
                f"graduation (current: {habit.scaffolding_status})"
            ],
        )

    # Resolve parameters with friction-aware defaults
    window, target, threshold = resolve_graduation_params(habit)

    # Apply re-scaffold tightening if applicable
    if habit.re_scaffold_count > 0:
        window, target, threshold = apply_re_scaffold_tightening(
            window,
            target,
            threshold,
            habit.re_scaffold_count,
        )

    now = datetime.now(tz=UTC)

    # Compute days accountable
    if habit.accountable_since is not None:
        days_accountable = (now.date() - habit.accountable_since).days
    else:
        days_accountable = 0

    meets_threshold = days_accountable >= threshold

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
            days_accountable=days_accountable,
            threshold_days=threshold,
            meets_rate=False,
            meets_threshold=meets_threshold,
            blocking_reasons=["No notification data in evaluation window"],
        )

    already_done_count = sum(1 for n in notifications if n.response == "Already done")
    current_rate = already_done_count / total_notifications

    meets_rate = current_rate >= target

    # Build blocking reasons
    blocking_reasons: list[str] = []
    if not meets_rate:
        blocking_reasons.append(f"Rate {current_rate:.0%} below target {target:.0%}")
    if not meets_threshold:
        blocking_reasons.append(
            f"{days_accountable} days accountable, need {threshold}"
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
        days_accountable=days_accountable,
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
                "Habit does not meet graduation criteria. " + "; ".join(evaluation.blocking_reasons)
            ),
        )

    # Execute transition
    habit.scaffolding_status = "graduated"
    habit.notification_frequency = "graduated"
    habit.graduated_at = datetime.now(tz=UTC)

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
                f"Frequency '{habit.notification_frequency}' is not in the step-down progression"
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
    already_done_count = sum(1 for n in notifications if n.response == "Already done")
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
            reasons=[f"Rate {rate:.0%} below step-down threshold {STEP_DOWN_RATE_THRESHOLD:.0%}"],
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
            f"Notification frequency stepped down: {habit.title}. {previous} → {new_frequency}."
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
        message=(f"Frequency stepped down for '{habit.title}': {previous} → {new_frequency}"),
    )


# ===========================================================================
# [2G-04] Slip Detection & Re-Scaffolding
# ===========================================================================

# Detection window and thresholds
SLIP_DETECTION_WINDOW_DAYS = 14
CHECKLIST_WARNING_THRESHOLD = 3
CHECKLIST_CRITICAL_THRESHOLD = 5
COMPLETION_WARNING_DAYS = 7  # 0 completions in this many days → warning
COMPLETION_CRITICAL_DAYS = 14  # 0 completions in this many days → critical


class SlipSignal(BaseModel):
    """A single signal indicating potential habit regression."""

    signal_type: str  # "missed_in_checklist" | "no_completion_recorded"
    detail: str
    severity: str  # "warning" | "critical"


class SlipDetectionResult(BaseModel):
    """Result of evaluating a graduated habit for slip signals."""

    slip_detected: bool
    habit_id: UUID
    habit_name: str
    slip_signals: list[SlipSignal]
    recommendation: str  # "re_scaffold" | "monitor" | "no_action"
    days_since_graduation: int
    message: str


class ReScaffoldResult(BaseModel):
    """Result of executing a habit re-scaffolding."""

    success: bool
    habit_id: UUID
    previous_scaffolding_status: str
    previous_notification_frequency: str
    new_notification_frequency: str
    re_scaffold_count: int
    tightened_params: dict
    message: str


def evaluate_graduated_habit_slip(
    db: Session,
    habit_id: UUID,
) -> SlipDetectionResult:
    """Evaluate whether a graduated habit is showing signs of regression.

    Read-only — returns recommendations but does not trigger re-scaffolding.
    The caller decides what to do with the result.
    """
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if habit is None:
        raise ValueError(f"Habit {habit_id} not found")

    # Gate: only graduated habits are evaluated for slip
    if habit.scaffolding_status != "graduated":
        return SlipDetectionResult(
            slip_detected=False,
            habit_id=habit_id,
            habit_name=habit.title,
            slip_signals=[],
            recommendation="no_action",
            days_since_graduation=0,
            message="Habit is not graduated — slip detection does not apply",
        )

    now = datetime.now(tz=UTC)
    window_start = now - timedelta(days=SLIP_DETECTION_WINDOW_DAYS)

    # Compute days since graduation using dedicated graduated_at column
    days_since_graduation = 0
    if habit.graduated_at is not None:
        grad_ts = habit.graduated_at
        if grad_ts.tzinfo is None:
            grad_ts = grad_ts.replace(tzinfo=UTC)
        days_since_graduation = (now - grad_ts).days

    signals: list[SlipSignal] = []

    # Signal 1: Missed in routine checklists (only for habits with a routine)
    if habit.routine_id is not None:
        checklist_notifications = (
            db.query(NotificationQueue)
            .filter(
                NotificationQueue.target_entity_type == "routine",
                NotificationQueue.target_entity_id == habit.routine_id,
                NotificationQueue.notification_type == "routine_checklist",
                NotificationQueue.scheduled_at >= window_start,
                NotificationQueue.status.in_(["responded", "expired"]),
            )
            .all()
        )

        miss_count = sum(
            1 for n in checklist_notifications if n.response == "Partial" or n.status == "expired"
        )

        if miss_count >= CHECKLIST_CRITICAL_THRESHOLD:
            signals.append(
                SlipSignal(
                    signal_type="missed_in_checklist",
                    detail=(
                        f"{miss_count} partial/expired routine checklists in "
                        f"the last {SLIP_DETECTION_WINDOW_DAYS} days"
                    ),
                    severity="critical",
                )
            )
        elif miss_count >= CHECKLIST_WARNING_THRESHOLD:
            signals.append(
                SlipSignal(
                    signal_type="missed_in_checklist",
                    detail=(
                        f"{miss_count} partial/expired routine checklists in "
                        f"the last {SLIP_DETECTION_WINDOW_DAYS} days"
                    ),
                    severity="warning",
                )
            )

    # Signal 2: No completion recorded
    window_7 = now - timedelta(days=COMPLETION_WARNING_DAYS)

    completions_14d = (
        db.query(sa_func.count(HabitCompletion.id))
        .filter(
            HabitCompletion.habit_id == habit_id,
            HabitCompletion.completed_at >= window_start.date(),
        )
        .scalar()
    )

    if completions_14d == 0:
        # Zero completions in full 14-day window → critical
        signals.append(
            SlipSignal(
                signal_type="no_completion_recorded",
                detail=(f"No completions recorded in the last {SLIP_DETECTION_WINDOW_DAYS} days"),
                severity="critical",
            )
        )
    else:
        completions_7d = (
            db.query(sa_func.count(HabitCompletion.id))
            .filter(
                HabitCompletion.habit_id == habit_id,
                HabitCompletion.completed_at >= window_7.date(),
            )
            .scalar()
        )

        if completions_7d == 0:
            # Zero completions in last 7 days but some in 14-day window → warning
            signals.append(
                SlipSignal(
                    signal_type="no_completion_recorded",
                    detail=(
                        f"No completions in the last {COMPLETION_WARNING_DAYS} days "
                        f"(last completion was more than a week ago)"
                    ),
                    severity="warning",
                )
            )

    # Determine recommendation
    has_critical = any(s.severity == "critical" for s in signals)
    has_warning = any(s.severity == "warning" for s in signals)

    if has_critical:
        recommendation = "re_scaffold"
    elif has_warning:
        recommendation = "monitor"
    else:
        recommendation = "no_action"

    # Build human-readable message
    if recommendation == "re_scaffold":
        message = (
            f"Habit '{habit.title}' is showing critical signs of regression. "
            f"Re-scaffolding recommended."
        )
    elif recommendation == "monitor":
        message = (
            f"Habit '{habit.title}' has early warning signs of slipping. "
            f"Monitor during next session."
        )
    else:
        message = f"Habit '{habit.title}' is holding steady after graduation."

    return SlipDetectionResult(
        slip_detected=len(signals) > 0,
        habit_id=habit_id,
        habit_name=habit.title,
        slip_signals=signals,
        recommendation=recommendation,
        days_since_graduation=days_since_graduation,
        message=message,
    )


def evaluate_all_graduated_habits(
    db: Session,
) -> list[SlipDetectionResult]:
    """Evaluate all active graduated habits for slip signals.

    Returns only habits that need attention (recommendation != 'no_action').
    This is the function the scheduler calls periodically.
    """
    habits = (
        db.query(Habit)
        .filter(
            Habit.scaffolding_status == "graduated",
            Habit.status == "active",
        )
        .all()
    )

    results = []
    for habit in habits:
        result = evaluate_graduated_habit_slip(db, habit.id)
        if result.recommendation != "no_action":
            results.append(result)
    return results


def re_scaffold_habit(
    db: Session,
    habit_id: UUID,
) -> ReScaffoldResult:
    """Execute re-scaffolding: reverse graduation and return to daily notifications.

    Increments re_scaffold_count so future graduation criteria are tightened.
    Does NOT reset streaks — historical achievement is preserved.
    """
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    if habit.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot re-scaffold a habit with status '{habit.status}' — must be 'active'",
        )

    if habit.scaffolding_status != "graduated":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot re-scaffold from scaffolding_status '{habit.scaffolding_status}' "
                "— must be 'graduated'"
            ),
        )

    # Snapshot previous values
    previous_scaffolding = habit.scaffolding_status
    previous_frequency = habit.notification_frequency

    # Reverse graduation
    habit.scaffolding_status = "accountable"
    habit.notification_frequency = "daily"
    habit.graduated_at = None

    # Increment re-scaffold count
    habit.re_scaffold_count += 1

    # Reset cooldown timer
    habit.last_frequency_changed_at = datetime.now(tz=UTC)

    # Compute tightened criteria for informational purposes
    window, target, threshold = resolve_graduation_params(habit)
    window, target, threshold = apply_re_scaffold_tightening(
        window,
        target,
        threshold,
        habit.re_scaffold_count,
    )
    tightened_params = {
        "window_days": window,
        "target_rate": target,
        "threshold_days": threshold,
    }

    # Log activity entry
    activity = ActivityLog(
        action_type="reflected",
        notes=(
            f"Habit re-scaffolded: {habit.title} "
            f"(re-scaffold #{habit.re_scaffold_count}). "
            f"Returning to daily notifications. "
            f"Next graduation requires: {window}d window, "
            f"{target:.0%} rate, {threshold}d minimum."
        ),
        habit_id=habit_id,
    )
    db.add(activity)
    db.commit()
    db.refresh(habit)

    return ReScaffoldResult(
        success=True,
        habit_id=habit_id,
        previous_scaffolding_status=previous_scaffolding,
        previous_notification_frequency=previous_frequency,
        new_notification_frequency="daily",
        re_scaffold_count=habit.re_scaffold_count,
        tightened_params=tightened_params,
        message=(
            f"Habit '{habit.title}' re-scaffolded "
            f"(#{habit.re_scaffold_count}). "
            f"Returning to daily notifications."
        ),
    )


# ===========================================================================
# [2G-05] Stacking Recommendation Engine
# ===========================================================================

STABILITY_MIN_ACCOUNTABLE_DAYS = 14
STABILITY_NO_MISS_WINDOW_DAYS = 7


class HabitStabilityInfo(BaseModel):
    """Stability assessment for an accountable habit."""

    habit_id: UUID
    habit_name: str
    scaffolding_status: str
    notification_frequency: str
    is_stable: bool
    stability_detail: str


class SuggestedHabit(BaseModel):
    """A habit recommended for introduction into the accountability loop."""

    habit_id: UUID
    habit_name: str
    source: str  # "queued" | "paused"
    reason: str


class StackingRecommendation(BaseModel):
    """Result of evaluating a routine's readiness for a new accountable habit."""

    ready: bool
    routine_id: UUID
    routine_name: str
    active_accountable_habits: list[HabitStabilityInfo]
    blocking_habits: list[HabitStabilityInfo]
    suggested_next: SuggestedHabit | None
    message: str


def _assess_habit_stability(
    db: Session,
    habit: Habit,
) -> HabitStabilityInfo:
    """Assess whether an accountable habit is stable enough to allow stacking.

    Uses evaluate_frequency_step_down() in read-only mode to get the current
    "already done" rate, then applies stability criteria.
    """
    # Already at weekly — stable by definition (stepped down to minimum)
    if habit.notification_frequency == "weekly":
        return HabitStabilityInfo(
            habit_id=habit.id,
            habit_name=habit.title,
            scaffolding_status=habit.scaffolding_status,
            notification_frequency=habit.notification_frequency,
            is_stable=True,
            stability_detail="At minimum frequency (weekly)",
        )

    # Use step-down evaluation to get the "already done" rate
    step_result = evaluate_frequency_step_down(db, habit.id)
    rate = step_result.current_rate

    # Stable if rate >= 60% (step-down threshold)
    if rate >= STEP_DOWN_RATE_THRESHOLD:
        return HabitStabilityInfo(
            habit_id=habit.id,
            habit_name=habit.title,
            scaffolding_status=habit.scaffolding_status,
            notification_frequency=habit.notification_frequency,
            is_stable=True,
            stability_detail=f"Step-down eligible ({rate:.0%} already-done rate)",
        )

    # Stable if accountable for 14+ days with no missed completions in last 7
    now = datetime.now(tz=UTC)
    if habit.accountable_since is not None:
        days_accountable = (now.date() - habit.accountable_since).days
        if days_accountable >= STABILITY_MIN_ACCOUNTABLE_DAYS:
            window_start = now.date() - timedelta(
                days=STABILITY_NO_MISS_WINDOW_DAYS,
            )
            completions_7d = (
                db.query(sa_func.count(HabitCompletion.id))
                .filter(
                    HabitCompletion.habit_id == habit.id,
                    HabitCompletion.completed_at >= window_start,
                )
                .scalar()
            )
            # "No missed completions" — at least one completion per day
            # for the last 7 days
            if completions_7d >= STABILITY_NO_MISS_WINDOW_DAYS:
                return HabitStabilityInfo(
                    habit_id=habit.id,
                    habit_name=habit.title,
                    scaffolding_status=habit.scaffolding_status,
                    notification_frequency=habit.notification_frequency,
                    is_stable=True,
                    stability_detail=(
                        f"Accountable {days_accountable} days, "
                        f"no missed completions in last "
                        f"{STABILITY_NO_MISS_WINDOW_DAYS} days"
                    ),
                )

    # Not stable — blocking
    detail_parts = [f"{rate:.0%} already-done rate"]
    if habit.accountable_since is not None:
        days = (now.date() - habit.accountable_since).days
        detail_parts.append(f"{days} days accountable")
    return HabitStabilityInfo(
        habit_id=habit.id,
        habit_name=habit.title,
        scaffolding_status=habit.scaffolding_status,
        notification_frequency=habit.notification_frequency,
        is_stable=False,
        stability_detail="Not yet stable: " + ", ".join(detail_parts),
    )


def get_stacking_recommendation(
    db: Session,
    routine_id: UUID,
) -> StackingRecommendation:
    """Evaluate whether a routine is ready for a new accountable habit.

    Assesses stability of all current accountable habits, determines readiness,
    and suggests the next habit to introduce if ready. Read-only — does not
    modify any state.
    """
    routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")

    # Load all habits in this routine
    active_habits = (
        db.query(Habit).filter(Habit.routine_id == routine_id, Habit.status == "active").all()
    )
    paused_habits = (
        db.query(Habit).filter(Habit.routine_id == routine_id, Habit.status == "paused").all()
    )

    # Freeform routine: no habits at all
    if not active_habits and not paused_habits:
        return StackingRecommendation(
            ready=True,
            routine_id=routine_id,
            routine_name=routine.title,
            active_accountable_habits=[],
            blocking_habits=[],
            suggested_next=None,
            message=("This is a freeform routine with no habits. Stacking doesn't apply."),
        )

    # Assess stability of accountable habits
    accountable_habits = [h for h in active_habits if h.scaffolding_status == "accountable"]
    stability_infos: list[HabitStabilityInfo] = []
    blocking: list[HabitStabilityInfo] = []

    for habit in accountable_habits:
        info = _assess_habit_stability(db, habit)
        stability_infos.append(info)
        if not info.is_stable:
            blocking.append(info)

    # Determine readiness
    ready = len(blocking) == 0

    # No accountable habits — ready for first one
    if not accountable_habits:
        ready = True

    # Suggest next habit if ready
    suggested_next: SuggestedHabit | None = None

    if ready:
        # Priority 1: Paused habits with scaffolding_status='tracking',
        # ordered by accountable_since (oldest first)
        paused_tracking = [h for h in paused_habits if h.scaffolding_status == "tracking"]
        paused_tracking.sort(
            key=lambda h: (
                h.position if h.position is not None else float("inf"),
                h.accountable_since or datetime.min.date(),
            ),
        )

        if paused_tracking:
            pick = paused_tracking[0]
            suggested_next = SuggestedHabit(
                habit_id=pick.id,
                habit_name=pick.title,
                source="paused",
                reason=(
                    "Previously started but paused — resuming is preferred "
                    "over starting something new"
                ),
            )
        else:
            # Priority 2: Active tracking habits, ordered by position then created_at
            active_tracking = [h for h in active_habits if h.scaffolding_status == "tracking"]
            active_tracking.sort(
                key=lambda h: (
                    h.position if h.position is not None else float("inf"),
                    h.created_at,
                ),
            )

            if active_tracking:
                pick = active_tracking[0]
                suggested_next = SuggestedHabit(
                    habit_id=pick.id,
                    habit_name=pick.title,
                    source="queued",
                    reason="Next in routine order",
                )

    # Build context-appropriate message
    if not ready:
        # Pick first blocking habit for message
        blocker = blocking[0]
        rate_str = blocker.stability_detail
        message = (
            f"Hold steady — {blocker.habit_name} needs more time before "
            f"adding another habit. {rate_str}."
        )
    elif not accountable_habits:
        message = (
            f"No habits are in the accountability loop for "
            f"{routine.title} yet. Pick one to start with."
        )
    elif suggested_next is not None:
        message = (
            f"You've been consistent with your current habits. "
            f"Ready to add {suggested_next.habit_name} to {routine.title}?"
        )
    else:
        message = f"All habits in {routine.title} are in the scaffolding pipeline. Nice work."

    return StackingRecommendation(
        ready=ready,
        routine_id=routine_id,
        routine_name=routine.title,
        active_accountable_habits=stability_infos,
        blocking_habits=blocking,
        suggested_next=suggested_next,
        message=message,
    )
