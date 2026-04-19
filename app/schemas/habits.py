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

"""Pydantic schemas for Habit CRUD operations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

HabitStatus = Literal["active", "paused", "graduated", "abandoned"]
HabitFrequency = Literal["daily", "weekdays", "weekends", "weekly", "custom"]
NotificationFrequency = Literal[
    "daily", "every_other_day", "twice_week", "weekly", "graduated", "none"
]
ScaffoldingStatus = Literal["tracking", "accountable", "graduated"]


class HabitCreate(BaseModel):
    """Fields required to create a habit."""

    routine_id: UUID | None = None
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: HabitStatus = "active"
    frequency: HabitFrequency | None = None
    notification_frequency: NotificationFrequency = "none"
    scaffolding_status: ScaffoldingStatus = "tracking"
    accountable_since: date | None = None
    graduation_window: int | None = None
    graduation_target: float | None = None
    graduation_threshold: int | None = None
    friction_score: int | None = None
    position: int | None = None

    @field_validator("graduation_target")
    @classmethod
    def validate_graduation_target(cls, v: float | None) -> float | None:
        if v is not None and (v < 0.0 or v > 1.0):
            msg = "graduation_target must be between 0.0 and 1.0"
            raise ValueError(msg)
        return v

    @field_validator("friction_score")
    @classmethod
    def validate_friction_score(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            msg = "friction_score must be between 1 and 5"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def standalone_requires_frequency(self) -> HabitCreate:
        """Standalone habits (no routine_id) must specify a frequency."""
        if self.routine_id is None and self.frequency is None:
            raise ValueError("frequency is required for standalone habits (no routine_id)")
        return self


class HabitUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    routine_id: UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: HabitStatus | None = None
    frequency: HabitFrequency | None = None
    notification_frequency: NotificationFrequency | None = None
    scaffolding_status: ScaffoldingStatus | None = None
    accountable_since: date | None = None
    graduation_window: int | None = None
    graduation_target: float | None = None
    graduation_threshold: int | None = None
    friction_score: int | None = None
    position: int | None = None

    @field_validator("graduation_target")
    @classmethod
    def validate_graduation_target(cls, v: float | None) -> float | None:
        if v is not None and (v < 0.0 or v > 1.0):
            msg = "graduation_target must be between 0.0 and 1.0"
            raise ValueError(msg)
        return v

    @field_validator("friction_score")
    @classmethod
    def validate_friction_score(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            msg = "friction_score must be between 1 and 5"
            raise ValueError(msg)
        return v


class EffectiveGraduationParams(BaseModel):
    """Resolved graduation parameters surfaced on habit responses (Amendment 05).

    Composite of `resolve_graduation_params` + `apply_re_scaffold_tightening`.
    Read-only: computed at serialization time, not stored and not settable.
    """

    window_days: int
    target_rate: float
    threshold_days: int
    source: Literal["override", "friction_default"]


class HabitResponse(BaseModel):
    """Habit returned from API — includes id and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    routine_id: UUID | None = None
    title: str
    description: str | None = None
    status: HabitStatus
    frequency: HabitFrequency | None = None
    notification_frequency: NotificationFrequency
    scaffolding_status: ScaffoldingStatus
    accountable_since: date | None = None
    graduation_window: int | None = None
    graduation_target: float | None = None
    graduation_threshold: int | None = None
    friction_score: int | None = None
    position: int | None = None
    re_scaffold_count: int
    last_frequency_changed_at: datetime | None = None
    graduated_at: datetime | None = None
    current_streak: int
    best_streak: int
    last_completed: date | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def effective_graduation_params(self) -> EffectiveGraduationParams:
        """Resolved graduation params — overrides or friction defaults, plus tightening."""
        # Local imports keep schemas → services dependency one-way at module
        # load time; resolve_graduation_params uses TYPE_CHECKING for Habit so
        # duck-typing this Pydantic model is safe — it reads the same four
        # attrs (friction_score + three override columns).
        from app.services.graduation import apply_re_scaffold_tightening
        from app.services.graduation_defaults import resolve_graduation_params

        window, target, threshold = resolve_graduation_params(self)
        if self.re_scaffold_count > 0:
            window, target, threshold = apply_re_scaffold_tightening(
                window, target, threshold, self.re_scaffold_count,
            )
        has_override = (
            self.graduation_window is not None
            or self.graduation_target is not None
            or self.graduation_threshold is not None
        )
        return EffectiveGraduationParams(
            window_days=window,
            target_rate=target,
            threshold_days=threshold,
            source="override" if has_override else "friction_default",
        )


class HabitDetailResponse(HabitResponse):
    """Habit with nested parent routine — returned by GET /api/habits/{id}."""

    routine: RoutineResponse | None = None


class HabitListResponse(BaseModel):
    """Envelope for GET /api/habits/ — wraps the item list with a count."""

    items: list[HabitResponse]
    count: int


# ---------------------------------------------------------------------------
# Habit Completion — POST /api/habits/{id}/complete
# ---------------------------------------------------------------------------


class HabitCompleteRequest(BaseModel):
    """Optional payload for habit completion."""

    completed_date: date | None = None
    notes: str | None = Field(default=None, max_length=5000)


class HabitCompleteResponse(BaseModel):
    """Response from completing a habit."""

    model_config = ConfigDict(from_attributes=True)

    habit_id: UUID
    completion_id: UUID
    completed_date: date
    current_streak: int
    best_streak: int
    streak_was_broken: bool
    source: str


from app.schemas.routines import RoutineResponse  # noqa: E402

HabitDetailResponse.model_rebuild()
