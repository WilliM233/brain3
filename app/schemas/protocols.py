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

"""Pydantic schemas for Protocol CRUD operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProtocolStep(BaseModel):
    """Single step within a protocol — validated but stored as JSONB."""

    order: int = Field(ge=1)
    title: str = Field(max_length=200)
    instruction: str = Field(max_length=2000)
    is_optional: bool = False


class ProtocolCreate(BaseModel):
    """Fields required to create a protocol."""

    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    steps: list[ProtocolStep] | None = Field(default=None, max_length=50)
    artifact_id: UUID | None = None
    is_seedable: bool = True
    tag_ids: list[UUID] | None = None


class ProtocolUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    steps: list[ProtocolStep] | None = Field(default=None, max_length=50)
    artifact_id: UUID | None = None
    is_seedable: bool | None = None


class ProtocolResponse(BaseModel):
    """Protocol returned from list and create endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    steps: list[ProtocolStep] | None = None
    artifact_id: UUID | None = None
    is_seedable: bool
    version: int
    created_at: datetime
    updated_at: datetime
    tags: list["TagResponse"] = []


class ProtocolDetailResponse(ProtocolResponse):
    """Single protocol with resolved artifact relationship."""

    artifact: "ArtifactResponse | None" = None


from app.schemas.artifacts import ArtifactResponse  # noqa: E402
from app.schemas.tags import TagResponse  # noqa: E402

ProtocolResponse.model_rebuild()
ProtocolDetailResponse.model_rebuild()
