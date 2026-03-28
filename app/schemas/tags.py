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
