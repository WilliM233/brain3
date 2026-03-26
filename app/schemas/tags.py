"""Pydantic schemas for Tag CRUD operations."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TagCreate(BaseModel):
    """Fields required to create a tag."""

    name: str
    color: str | None = None


class TagUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    name: str | None = None
    color: str | None = None


class TagResponse(BaseModel):
    """Tag returned from API — includes id."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    color: str | None = None
