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

"""Pure streak evaluation logic for routine completions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class StreakResult:
    """Outcome of a streak evaluation."""

    current_streak: int
    best_streak: int
    streak_was_broken: bool


def _count_weekdays_between(start: date, end: date) -> int:
    """Count weekdays in the half-open interval (start, end]."""
    if end <= start:
        return 0
    total_days = (end - start).days
    full_weeks, remainder = divmod(total_days, 7)
    count = full_weeks * 5
    for i in range(1, remainder + 1):
        if (start + timedelta(days=i)).weekday() < 5:
            count += 1
    return count


def _count_weekend_days_between(start: date, end: date) -> int:
    """Count weekend days (Sat/Sun) in the half-open interval (start, end]."""
    if end <= start:
        return 0
    total_days = (end - start).days
    full_weeks, remainder = divmod(total_days, 7)
    count = full_weeks * 2
    for i in range(1, remainder + 1):
        if (start + timedelta(days=i)).weekday() >= 5:
            count += 1
    return count


def _max_gap_for_custom(scheduled_days: list[int]) -> int:
    """Longest gap in calendar days between consecutive scheduled days.

    ``scheduled_days`` uses Monday=0 … Sunday=6.  Falls back to 7 (weekly)
    when no schedule entries are provided.
    """
    if not scheduled_days:
        return 7
    days = sorted(set(scheduled_days))
    if len(days) == 1:
        return 7
    gaps = [days[i + 1] - days[i] for i in range(len(days) - 1)]
    gaps.append(7 - days[-1] + days[0])  # wrap-around gap
    return max(gaps)


def evaluate_streak(
    frequency: str,
    current_streak: int,
    best_streak: int,
    last_completed: date | None,
    completed_date: date,
    scheduled_days: list[int] | None = None,
) -> StreakResult:
    """Evaluate whether a routine completion continues or breaks the streak.

    Returns a ``StreakResult`` with updated streak counters and a flag
    indicating whether the streak was broken.
    """
    # First-ever completion
    if last_completed is None:
        return StreakResult(
            current_streak=1,
            best_streak=max(best_streak, 1),
            streak_was_broken=False,
        )

    # Same-day duplicate — idempotent, no change
    if completed_date == last_completed:
        return StreakResult(
            current_streak=current_streak,
            best_streak=best_streak,
            streak_was_broken=False,
        )

    # Backdating before last_completed — no retroactive recalculation
    if completed_date < last_completed:
        return StreakResult(
            current_streak=current_streak,
            best_streak=best_streak,
            streak_was_broken=False,
        )

    # Determine whether the streak continues
    continues = False
    if frequency == "daily":
        continues = (completed_date - last_completed).days == 1
    elif frequency == "weekdays":
        continues = _count_weekdays_between(last_completed, completed_date) == 1
    elif frequency == "weekends":
        continues = _count_weekend_days_between(last_completed, completed_date) == 1
    elif frequency == "weekly":
        continues = 1 <= (completed_date - last_completed).days <= 7
    elif frequency == "custom":
        max_gap = _max_gap_for_custom(scheduled_days or [])
        continues = 1 <= (completed_date - last_completed).days <= max_gap

    if continues:
        new_streak = current_streak + 1
        return StreakResult(
            current_streak=new_streak,
            best_streak=max(best_streak, new_streak),
            streak_was_broken=False,
        )

    return StreakResult(
        current_streak=1,
        best_streak=max(best_streak, 1),
        streak_was_broken=True,
    )
