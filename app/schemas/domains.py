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

"""Pydantic schemas for Domain CRUD operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DomainCreate(BaseModel):
    """Fields required to create a domain."""

    name: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    color: str | None = Field(default=None, max_length=7)
    sort_order: int = 0


class DomainUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    color: str | None = Field(default=None, max_length=7)
    sort_order: int | None = None


class DomainResponse(BaseModel):
    """Domain returned from API — includes id and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    color: str | None = None
    sort_order: int | None = None
    created_at: datetime


class DomainDetailResponse(DomainResponse):
    """Domain with nested goals — returned by GET /api/domains/{id}."""

    goals: list[GoalResponse] = []


# Deferred import to avoid circular dependency
from app.schemas.goals import GoalResponse  # noqa: E402

DomainDetailResponse.model_rebuild()
