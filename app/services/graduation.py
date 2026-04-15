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

"""Graduation evaluation service — rolling-window analysis for habit scaffolding."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import Habit, NotificationQueue
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
