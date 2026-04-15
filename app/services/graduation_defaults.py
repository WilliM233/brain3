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

"""Friction-aware graduation defaults and parameter resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Habit

# friction_score: (window_days, target_rate, threshold_days)
GRADUATION_DEFAULTS: dict[int | None, tuple[int, float, int]] = {
    1: (30, 0.85, 30),
    2: (30, 0.85, 30),
    3: (45, 0.85, 45),
    4: (60, 0.80, 60),
    5: (60, 0.80, 60),
    None: (45, 0.85, 45),  # unknown friction falls to middle tier
}


def resolve_graduation_params(habit: Habit) -> tuple[int, float, int]:
    """Return (window, target, threshold) using per-habit overrides or friction defaults.

    Each of the three knobs resolves independently — a habit can override
    graduation_window but inherit graduation_target from its friction tier.
    """
    defaults = GRADUATION_DEFAULTS[habit.friction_score]
    window = habit.graduation_window if habit.graduation_window is not None else defaults[0]
    target = float(habit.graduation_target) if habit.graduation_target is not None else defaults[1]
    threshold = (
        habit.graduation_threshold if habit.graduation_threshold is not None else defaults[2]
    )
    return (window, target, threshold)
