"""Pydantic schemas for Goal CRUD operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GoalCreate(BaseModel):
    """Fields required to create a goal."""

    domain_id: UUID
    title: str
    description: str | None = None
    status: str = "active"


class GoalUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    domain_id: UUID | None = None
    title: str | None = None
    description: str | None = None
    status: str | None = None


class GoalResponse(BaseModel):
    """Goal returned from API — includes id and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    domain_id: UUID
    title: str
    description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectResponse(BaseModel):
    """Minimal project schema for nesting in GoalDetailResponse.

    Full schema comes in TICKET-05 — this forward-declares enough
    for the detail endpoint to work (returns empty list until then).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: str
    created_at: datetime


class GoalDetailResponse(GoalResponse):
    """Goal with nested projects — returned by GET /api/goals/{id}."""

    projects: list[ProjectResponse] = []
