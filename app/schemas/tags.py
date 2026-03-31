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

"""Pydantic schemas for Tag CRUD operations."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TagCreate(BaseModel):
    """Fields required to create a tag."""

    name: str = Field(max_length=100)
    color: str | None = Field(default=None, max_length=7)


class TagUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    name: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=7)


class TagResponse(BaseModel):
    """Tag returned from API — includes id."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    color: str | None = None
