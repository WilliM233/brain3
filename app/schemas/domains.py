"""Pydantic schemas for Domain CRUD operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DomainCreate(BaseModel):
    """Fields required to create a domain."""

    name: str
    description: str | None = None
    color: str | None = None
    sort_order: int = 0


class DomainUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    name: str | None = None
    description: str | None = None
    color: str | None = None
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
