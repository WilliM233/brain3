"""Pydantic schemas for State Check-in CRUD operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

CheckinType = Literal["morning", "midday", "evening", "micro", "freeform"]


class CheckinCreate(BaseModel):
    """Fields required to log a check-in. Only checkin_type is mandatory."""

    checkin_type: CheckinType
    energy_level: int | None = None
    mood: int | None = None
    focus_level: int | None = None
    freeform_note: str | None = None
    context: str | None = None

    @field_validator("energy_level", "mood", "focus_level")
    @classmethod
    def validate_1_to_5(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            msg = "Value must be between 1 and 5"
            raise ValueError(msg)
        return v


class CheckinUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    checkin_type: CheckinType | None = None
    energy_level: int | None = None
    mood: int | None = None
    focus_level: int | None = None
    freeform_note: str | None = None
    context: str | None = None

    @field_validator("energy_level", "mood", "focus_level")
    @classmethod
    def validate_1_to_5(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            msg = "Value must be between 1 and 5"
            raise ValueError(msg)
        return v


class CheckinResponse(BaseModel):
    """Check-in returned from API — includes id and logged_at timestamp."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    checkin_type: CheckinType
    energy_level: int | None = None
    mood: int | None = None
    focus_level: int | None = None
    freeform_note: str | None = None
    context: str | None = None
    logged_at: datetime
