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

"""Pydantic schemas for Notification Queue CRUD operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

NotificationType = Literal[
    "habit_nudge",
    "routine_checklist",
    "checkin_prompt",
    "time_block_reminder",
    "deadline_event_alert",
    "pattern_observation",
    "stale_work_nudge",
]

NotificationStatus = Literal["pending", "delivered", "responded", "expired"]

DeliveryType = Literal["notification"]

ScheduledBy = Literal["system", "claude", "rule"]


class NotificationCreate(BaseModel):
    """Fields required to create a notification."""

    notification_type: NotificationType
    delivery_type: DeliveryType = "notification"
    scheduled_at: datetime
    target_entity_type: str = Field(min_length=1)
    target_entity_id: UUID
    message: str = Field(min_length=1, max_length=2000)
    canned_responses: list[str] | None = None
    expires_at: datetime | None = None
    scheduled_by: ScheduledBy
    rule_id: UUID | None = None

    @field_validator("canned_responses")
    @classmethod
    def validate_canned_responses(
        cls, v: list[str] | None,
    ) -> list[str] | None:
        if v is None:
            return v
        if len(v) < 1 or len(v) > 10:
            msg = "canned_responses must contain 1-10 items"
            raise ValueError(msg)
        for item in v:
            if not isinstance(item, str) or len(item) < 1 or len(item) > 200:
                msg = "Each canned response must be a non-empty string up to 200 characters"
                raise ValueError(msg)
        return v


class NotificationUpdate(BaseModel):
    """Partial update fields for a notification. Immutable fields excluded."""

    delivery_type: DeliveryType | None = None
    status: NotificationStatus | None = None
    scheduled_at: datetime | None = None
    message: str | None = Field(default=None, min_length=1, max_length=2000)
    canned_responses: list[str] | None = None
    expires_at: datetime | None = None

    @field_validator("canned_responses")
    @classmethod
    def validate_canned_responses(
        cls, v: list[str] | None,
    ) -> list[str] | None:
        if v is None:
            return v
        if len(v) < 1 or len(v) > 10:
            msg = "canned_responses must contain 1-10 items"
            raise ValueError(msg)
        for item in v:
            if not isinstance(item, str) or len(item) < 1 or len(item) > 200:
                msg = "Each canned response must be a non-empty string up to 200 characters"
                raise ValueError(msg)
        return v


class NotificationResponse(BaseModel):
    """Notification returned from API — includes id and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    notification_type: str
    delivery_type: str
    status: str
    scheduled_at: datetime
    target_entity_type: str
    target_entity_id: UUID
    message: str
    canned_responses: list[str] | None = None
    response: str | None = None
    response_note: str | None = None
    responded_at: datetime | None = None
    expires_at: datetime | None = None
    scheduled_by: str
    rule_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
