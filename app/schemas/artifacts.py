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

"""Pydantic schemas for Artifact CRUD operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ArtifactType = Literal[
    "document", "protocol", "brief", "prompt", "template", "journal", "spec"
]


class ArtifactCreate(BaseModel):
    """Fields required to create an artifact."""

    title: str = Field(max_length=200)
    artifact_type: ArtifactType
    content: str = Field(max_length=500_000)
    parent_id: UUID | None = None
    is_seedable: bool = False
    tag_ids: list[UUID] | None = None

    @field_validator("content")
    @classmethod
    def validate_content_byte_length(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 524_288:
            raise ValueError("Content exceeds 512KB byte limit")
        return v


class ArtifactUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    title: str | None = Field(default=None, max_length=200)
    artifact_type: ArtifactType | None = None
    content: str | None = Field(default=None, max_length=500_000)
    parent_id: UUID | None = None
    is_seedable: bool | None = None

    @field_validator("content")
    @classmethod
    def validate_content_byte_length(cls, v: str | None) -> str | None:
        if v is not None and len(v.encode("utf-8")) > 524_288:
            raise ValueError("Content exceeds 512KB byte limit")
        return v


class ArtifactResponse(BaseModel):
    """Artifact metadata returned from list endpoints — no content."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    artifact_type: str
    content_size: int
    version: int
    parent_id: UUID | None = None
    is_seedable: bool
    created_at: datetime
    updated_at: datetime
    tags: list["TagResponse"] = []


class ArtifactDetailResponse(ArtifactResponse):
    """Single artifact with content and resolved parent."""

    content: str | None = None
    parent: ArtifactResponse | None = None


from app.schemas.tags import TagResponse  # noqa: E402

ArtifactResponse.model_rebuild()
ArtifactDetailResponse.model_rebuild()
