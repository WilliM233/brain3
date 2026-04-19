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

"""Pydantic schemas for Rules Engine CRUD operations."""

from __future__ import annotations

import string
from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Enums — Python str enums, mirrored as Postgres enums in the migration
# ---------------------------------------------------------------------------

NotificationType = Literal[
    "habit_nudge",
    "routine_checklist",
    "checkin_prompt",
    "time_block_reminder",
    "deadline_event_alert",
    "pattern_observation",
    "stale_work_nudge",
]


class RuleEntityType(str, Enum):
    habit = "habit"
    task = "task"
    routine = "routine"
    checkin = "checkin"


class RuleMetric(str, Enum):
    consecutive_skips = "consecutive_skips"
    days_untouched = "days_untouched"
    non_responses = "non_responses"
    streak_length = "streak_length"


class RuleOperator(str, Enum):
    """Comparison operators. Names are shorthand; values are DB-stored symbols."""
    gte = ">="
    lte = "<="
    eq = "=="


class RuleAction(str, Enum):
    create_notification = "create_notification"


# ---------------------------------------------------------------------------
# Template placeholder validation
# ---------------------------------------------------------------------------

ALLOWED_PLACEHOLDERS = frozenset({
    "entity_name",
    "entity_type",
    "metric_value",
    "threshold",
    "rule_name",
})

_formatter = string.Formatter()


def validate_message_template(template: str) -> str:
    """Parse a message template and reject unknown placeholders."""
    try:
        parsed = list(_formatter.parse(template))
    except (ValueError, KeyError) as exc:
        msg = f"Invalid template syntax: {exc}"
        raise ValueError(msg) from exc

    for _, field_name, _, _ in parsed:
        if field_name is None:
            continue
        # field_name may be "entity_name.attr" — only validate the root
        root = field_name.split(".")[0].split("[")[0]
        if root not in ALLOWED_PLACEHOLDERS:
            msg = (
                f"Unknown placeholder '{{{field_name}}}'. "
                f"Allowed: {sorted(ALLOWED_PLACEHOLDERS)}"
            )
            raise ValueError(msg)
    return template


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class RuleCreate(BaseModel):
    """Fields required to create a rule."""

    name: str = Field(min_length=1, max_length=200)
    entity_type: RuleEntityType
    entity_id: UUID | None = None
    metric: RuleMetric
    operator: RuleOperator
    threshold: int
    action: RuleAction = RuleAction.create_notification
    notification_type: NotificationType
    message_template: str = Field(min_length=1)
    enabled: bool = True
    cooldown_hours: int = 24
    is_default: bool = False

    @field_validator("message_template")
    @classmethod
    def check_template(cls, v: str) -> str:
        return validate_message_template(v)


class RuleUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    entity_type: RuleEntityType | None = None
    entity_id: UUID | None = None
    metric: RuleMetric | None = None
    operator: RuleOperator | None = None
    threshold: int | None = None
    action: RuleAction | None = None
    notification_type: NotificationType | None = None
    message_template: str | None = Field(default=None, min_length=1)
    enabled: bool | None = None
    cooldown_hours: int | None = None

    @field_validator("message_template")
    @classmethod
    def check_template(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_message_template(v)


class RuleRead(BaseModel):
    """Rule returned from API — includes id and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    entity_type: RuleEntityType
    entity_id: UUID | None = None
    metric: RuleMetric
    operator: RuleOperator
    threshold: int
    action: RuleAction
    notification_type: str
    message_template: str
    enabled: bool
    cooldown_hours: int
    is_default: bool
    last_triggered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RuleListResponse(BaseModel):
    """Envelope for GET /api/rules/ — wraps the item list with a count."""

    items: list[RuleRead]
    count: int


class RuleEvaluationResultResponse(BaseModel):
    """API response model for a rule evaluation result."""

    rule_id: UUID
    rule_name: str
    fired: bool
    reason: str
    notifications_created: int
    entities_evaluated: int
