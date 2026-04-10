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

"""CRUD endpoints for Artifacts."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Artifact, ArtifactTag, Tag
from app.schemas.artifacts import (
    ArtifactCreate,
    ArtifactDetailResponse,
    ArtifactResponse,
    ArtifactUpdate,
)
from app.schemas.tags import TagResponse

router = APIRouter()
artifact_tags_router = APIRouter()


# ---------------------------------------------------------------------------
# Artifact CRUD — /api/artifacts
# ---------------------------------------------------------------------------


@router.post("/", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
def create_artifact(payload: ArtifactCreate, db: Session = Depends(get_db)) -> Artifact:
    """Create a new artifact. Validates parent_id and tag_ids if provided."""
    if payload.parent_id is not None:
        if not db.query(Artifact).filter(Artifact.id == payload.parent_id).first():
            raise HTTPException(status_code=400, detail="Parent artifact not found")

    tags = []
    if payload.tag_ids:
        for tid in payload.tag_ids:
            tag = db.query(Tag).filter(Tag.id == tid).first()
            if not tag:
                raise HTTPException(status_code=400, detail=f"Tag {tid} not found")
            tags.append(tag)

    content_size = len(payload.content.encode("utf-8"))
    artifact = Artifact(
        **payload.model_dump(exclude={"tag_ids"}),
        content_size=content_size,
    )
    db.add(artifact)
    db.flush()

    for tag in tags:
        db.add(ArtifactTag(artifact_id=artifact.id, tag_id=tag.id))

    db.commit()
    db.refresh(artifact)
    return artifact


@router.get("/", response_model=list[ArtifactResponse])
def list_artifacts(
    artifact_type: str | None = Query(None),
    is_seedable: bool | None = Query(None),
    search: str | None = Query(None, description="Case-insensitive title search"),
    parent_id: UUID | None = Query(None, description="Children of a specific artifact"),
    tag: str | None = Query(None, description="Comma-separated tag names (AND logic)"),
    db: Session = Depends(get_db),
) -> list[Artifact]:
    """List artifacts (metadata only — no content). Supports composable filters."""
    query = db.query(Artifact)

    if artifact_type is not None:
        query = query.filter(Artifact.artifact_type == artifact_type)
    if is_seedable is not None:
        query = query.filter(Artifact.is_seedable == is_seedable)
    if search is not None:
        query = query.filter(Artifact.title.ilike(f"%{search}%"))
    if parent_id is not None:
        query = query.filter(Artifact.parent_id == parent_id)
    if tag is not None:
        tag_names = [t.strip().lower() for t in tag.split(",") if t.strip()]
        for tag_name in tag_names:
            query = query.filter(
                Artifact.tags.any(Tag.name == tag_name)
            )

    return query.order_by(Artifact.created_at.desc()).all()


@router.get("/{artifact_id}", response_model=ArtifactDetailResponse)
def get_artifact(artifact_id: UUID, db: Session = Depends(get_db)) -> Artifact:
    """Get a single artifact with content and resolved parent."""
    artifact = (
        db.query(Artifact)
        .options(
            joinedload(Artifact.tags),
            joinedload(Artifact.parent),
        )
        .filter(Artifact.id == artifact_id)
        .first()
    )
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.patch("/{artifact_id}", response_model=ArtifactDetailResponse)
def update_artifact(
    artifact_id: UUID, payload: ArtifactUpdate, db: Session = Depends(get_db)
) -> Artifact:
    """Partial update. Auto-increments version and recomputes content_size on content change."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    updates = payload.model_dump(exclude_unset=True)

    if "parent_id" in updates and updates["parent_id"] is not None:
        if not db.query(Artifact).filter(Artifact.id == updates["parent_id"]).first():
            raise HTTPException(status_code=400, detail="Parent artifact not found")

    if "content" in updates:
        content = updates["content"]
        if content is not None:
            updates["content_size"] = len(content.encode("utf-8"))
        else:
            updates["content_size"] = 0
        updates["version"] = artifact.version + 1

    for field, value in updates.items():
        setattr(artifact, field, value)

    db.commit()
    db.refresh(artifact)

    # Eager-load for detail response
    artifact = (
        db.query(Artifact)
        .options(
            joinedload(Artifact.tags),
            joinedload(Artifact.parent),
        )
        .filter(Artifact.id == artifact_id)
        .first()
    )
    return artifact


@router.delete("/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_artifact(artifact_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete an artifact. Children get parent_id set to NULL."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    db.delete(artifact)
    db.commit()


# ---------------------------------------------------------------------------
# Artifact-Tag attachment — /api/artifacts/{artifact_id}/tags
# ---------------------------------------------------------------------------


@artifact_tags_router.get("/{artifact_id}/tags", response_model=list[TagResponse])
def list_tags_on_artifact(
    artifact_id: UUID, db: Session = Depends(get_db)
) -> list[Tag]:
    """List all tags attached to an artifact."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact.tags


@artifact_tags_router.post(
    "/{artifact_id}/tags/{tag_id}", response_model=TagResponse,
)
def attach_tag_to_artifact(
    artifact_id: UUID, tag_id: UUID, db: Session = Depends(get_db)
) -> Tag:
    """Attach a tag to an artifact. Idempotent."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    existing = (
        db.query(ArtifactTag)
        .filter(ArtifactTag.artifact_id == artifact_id, ArtifactTag.tag_id == tag_id)
        .first()
    )
    if not existing:
        db.add(ArtifactTag(artifact_id=artifact_id, tag_id=tag_id))
        db.commit()

    return tag


@artifact_tags_router.delete(
    "/{artifact_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT,
)
def detach_tag_from_artifact(
    artifact_id: UUID, tag_id: UUID, db: Session = Depends(get_db)
) -> None:
    """Remove a tag from an artifact."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    link = (
        db.query(ArtifactTag)
        .filter(ArtifactTag.artifact_id == artifact_id, ArtifactTag.tag_id == tag_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Tag is not attached to this artifact")
    db.delete(link)
    db.commit()
