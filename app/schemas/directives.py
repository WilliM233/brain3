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

"""Pydantic schemas for Directive CRUD operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DirectiveCreate(BaseModel):
    """Fields required to create a directive."""

    name: str = Field(max_length=200)
    content: str = Field(max_length=10_000)
    scope: Literal["global", "skill", "agent"]
    scope_ref: UUID | None = None
    priority: int = Field(default=5, ge=1, le=10)
    is_seedable: bool = True
    tag_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def validate_scope_ref(self) -> "DirectiveCreate":
        if self.scope == "global" and self.scope_ref is not None:
            raise ValueError("scope_ref must be null for global directives")
        if self.scope in ("skill", "agent") and self.scope_ref is None:
            raise ValueError("scope_ref is required for skill and agent directives")
        return self


class DirectiveUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    name: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=10_000)
    scope: Literal["global", "skill", "agent"] | None = None
    scope_ref: UUID | None = None
    priority: int | None = Field(default=None, ge=1, le=10)
    is_seedable: bool | None = None


class DirectiveResponse(BaseModel):
    """Directive returned from list and create endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    content: str
    scope: str
    scope_ref: UUID | None
    priority: int
    is_seedable: bool
    created_at: datetime
    updated_at: datetime
    tags: list["TagResponse"] = []


class DirectiveResolveResponse(BaseModel):
    """Grouped directives from the resolve endpoint."""

    global_directives: list[DirectiveResponse]
    skill_directives: list[DirectiveResponse]
    agent_directives: list[DirectiveResponse]


from app.schemas.tags import TagResponse  # noqa: E402

DirectiveResponse.model_rebuild()
