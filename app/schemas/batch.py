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

"""Shared Pydantic schemas for batch API operations."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.activity import ActivityLogCreate, ActivityLogResponse
from app.schemas.artifacts import ArtifactCreate, ArtifactResponse
from app.schemas.directives import DirectiveCreate, DirectiveResponse
from app.schemas.protocols import ProtocolCreate, ProtocolResponse
from app.schemas.skills import SkillCreate, SkillResponse
from app.schemas.tasks import TaskCreate, TaskResponse

# ---------------------------------------------------------------------------
# Batch tag attachment — shared request schema
# ---------------------------------------------------------------------------


class BatchTagAttachRequest(BaseModel):
    """Attach multiple tags to an entity in one call."""

    tag_ids: list[UUID] = Field(max_length=100)


# ---------------------------------------------------------------------------
# Batch create — per-entity request schemas
# ---------------------------------------------------------------------------


class BatchTaskCreate(BaseModel):
    """Batch create tasks."""

    items: list[TaskCreate] = Field(max_length=100)


class BatchActivityCreate(BaseModel):
    """Batch create activity log entries."""

    items: list[ActivityLogCreate] = Field(max_length=100)


class BatchArtifactCreate(BaseModel):
    """Batch create artifacts."""

    items: list[ArtifactCreate] = Field(max_length=25)


class BatchProtocolCreate(BaseModel):
    """Batch create protocols."""

    items: list[ProtocolCreate] = Field(max_length=100)


class BatchDirectiveCreate(BaseModel):
    """Batch create directives."""

    items: list[DirectiveCreate] = Field(max_length=100)


class BatchSkillCreate(BaseModel):
    """Batch create skills."""

    items: list[SkillCreate] = Field(max_length=100)


# ---------------------------------------------------------------------------
# Batch create — per-entity response schemas
# ---------------------------------------------------------------------------


class BatchTaskCreateResponse(BaseModel):
    """Response for batch task creation."""

    created: list[TaskResponse]
    count: int


class BatchActivityCreateResponse(BaseModel):
    """Response for batch activity log creation."""

    created: list[ActivityLogResponse]
    count: int


class BatchArtifactCreateResponse(BaseModel):
    """Response for batch artifact creation."""

    created: list[ArtifactResponse]
    count: int


class BatchProtocolCreateResponse(BaseModel):
    """Response for batch protocol creation."""

    created: list[ProtocolResponse]
    count: int


class BatchDirectiveCreateResponse(BaseModel):
    """Response for batch directive creation."""

    created: list[DirectiveResponse]
    count: int


class BatchSkillCreateResponse(BaseModel):
    """Response for batch skill creation."""

    created: list[SkillResponse]
    count: int
