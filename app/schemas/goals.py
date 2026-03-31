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

"""Pydantic schemas for Goal CRUD operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

GoalStatus = Literal["active", "paused", "achieved", "abandoned"]


class GoalCreate(BaseModel):
    """Fields required to create a goal."""

    domain_id: UUID
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: GoalStatus = "active"


class GoalUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    domain_id: UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: GoalStatus | None = None


class GoalResponse(BaseModel):
    """Goal returned from API — includes id and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    domain_id: UUID
    title: str
    description: str | None = None
    status: GoalStatus
    created_at: datetime
    updated_at: datetime


class GoalDetailResponse(GoalResponse):
    """Goal with nested projects — returned by GET /api/goals/{id}."""

    projects: list[ProjectResponse] = []


from app.schemas.projects import ProjectResponse  # noqa: E402

GoalDetailResponse.model_rebuild()
