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

"""Pydantic schemas for Skill CRUD operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SkillCreate(BaseModel):
    """Fields required to create a skill."""

    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    adhd_patterns: str | None = Field(default=None, max_length=10_000)
    artifact_id: UUID | None = None
    is_seedable: bool = True
    is_default: bool = False
    domain_ids: list[UUID] | None = None
    protocol_ids: list[UUID] | None = None
    directive_ids: list[UUID] | None = None


class SkillUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    adhd_patterns: str | None = Field(default=None, max_length=10_000)
    artifact_id: UUID | None = None
    is_seedable: bool | None = None
    is_default: bool | None = None


class SkillResponse(BaseModel):
    """Skill returned from list and create endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    adhd_patterns: str | None
    artifact_id: UUID | None
    is_seedable: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    domains: list["DomainResponse"] = []
    protocols: list["ProtocolResponse"] = []
    directives: list["DirectiveResponse"] = []


class SkillDirectivesGrouped(BaseModel):
    """Directives grouped by scope for get_skill_full."""

    global_directives: list["DirectiveResponse"]
    skill: list["DirectiveResponse"]


class SkillFullResponse(BaseModel):
    """Resolved skill view — protocols, grouped directives, domains, artifact."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    adhd_patterns: str | None
    is_seedable: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    artifact: "ArtifactResponse | None" = None
    domains: list["DomainResponse"] = []
    protocols: list["ProtocolResponse"] = []
    directives: SkillDirectivesGrouped


from app.schemas.artifacts import ArtifactResponse  # noqa: E402
from app.schemas.directives import DirectiveResponse  # noqa: E402
from app.schemas.domains import DomainResponse  # noqa: E402
from app.schemas.protocols import ProtocolResponse  # noqa: E402

SkillResponse.model_rebuild()
SkillDirectivesGrouped.model_rebuild()
SkillFullResponse.model_rebuild()
