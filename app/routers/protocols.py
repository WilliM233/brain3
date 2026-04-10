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

"""CRUD endpoints for Protocols."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Artifact, Protocol, ProtocolTag, Tag
from app.schemas.protocols import (
    ProtocolCreate,
    ProtocolDetailResponse,
    ProtocolResponse,
    ProtocolUpdate,
)
from app.schemas.tags import TagResponse

router = APIRouter()
protocol_tags_router = APIRouter()


# ---------------------------------------------------------------------------
# Protocol CRUD — /api/protocols
# ---------------------------------------------------------------------------


@router.post("/", response_model=ProtocolResponse, status_code=status.HTTP_201_CREATED)
def create_protocol(payload: ProtocolCreate, db: Session = Depends(get_db)) -> Protocol:
    """Create a new protocol. Validates artifact_id and tag_ids if provided."""
    # Unique name check
    existing = db.query(Protocol).filter(Protocol.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Protocol name already exists")

    if payload.artifact_id is not None:
        if not db.query(Artifact).filter(Artifact.id == payload.artifact_id).first():
            raise HTTPException(status_code=400, detail="Artifact not found")

    tags = []
    if payload.tag_ids:
        for tid in payload.tag_ids:
            tag = db.query(Tag).filter(Tag.id == tid).first()
            if not tag:
                raise HTTPException(status_code=400, detail=f"Tag {tid} not found")
            tags.append(tag)

    # Serialize steps to dicts for JSONB storage
    steps_data = None
    if payload.steps is not None:
        steps_data = [s.model_dump() for s in payload.steps]

    protocol = Protocol(
        **payload.model_dump(exclude={"tag_ids", "steps"}),
        steps=steps_data,
    )
    db.add(protocol)
    db.flush()

    for tag in tags:
        db.add(ProtocolTag(protocol_id=protocol.id, tag_id=tag.id))

    db.commit()
    db.refresh(protocol)
    return protocol


@router.get("/", response_model=list[ProtocolResponse])
def list_protocols(
    search: str | None = Query(None, description="Case-insensitive name search"),
    is_seedable: bool | None = Query(None),
    has_artifact: bool | None = Query(None, description="Filter by whether artifact_id is set"),
    tag: str | None = Query(None, description="Comma-separated tag names (AND logic)"),
    db: Session = Depends(get_db),
) -> list[Protocol]:
    """List protocols with composable filters."""
    query = db.query(Protocol)

    if search is not None:
        query = query.filter(Protocol.name.ilike(f"%{search}%"))
    if is_seedable is not None:
        query = query.filter(Protocol.is_seedable == is_seedable)
    if has_artifact is True:
        query = query.filter(Protocol.artifact_id.isnot(None))
    elif has_artifact is False:
        query = query.filter(Protocol.artifact_id.is_(None))
    if tag is not None:
        tag_names = [t.strip().lower() for t in tag.split(",") if t.strip()]
        for tag_name in tag_names:
            query = query.filter(
                Protocol.tags.any(Tag.name == tag_name)
            )

    return query.order_by(Protocol.created_at.desc()).all()


@router.get("/{protocol_id}", response_model=ProtocolDetailResponse)
def get_protocol(protocol_id: UUID, db: Session = Depends(get_db)) -> Protocol:
    """Get a single protocol with resolved artifact."""
    protocol = (
        db.query(Protocol)
        .options(
            joinedload(Protocol.tags),
            joinedload(Protocol.artifact),
        )
        .filter(Protocol.id == protocol_id)
        .first()
    )
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return protocol


@router.patch("/{protocol_id}", response_model=ProtocolDetailResponse)
def update_protocol(
    protocol_id: UUID, payload: ProtocolUpdate, db: Session = Depends(get_db)
) -> Protocol:
    """Partial update. Auto-increments version when steps or description change."""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")

    updates = payload.model_dump(exclude_unset=True)

    # Unique name check on update
    if "name" in updates and updates["name"] is not None:
        conflict = (
            db.query(Protocol)
            .filter(Protocol.name == updates["name"], Protocol.id != protocol_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail="Protocol name already exists")

    # Validate artifact_id if provided
    if "artifact_id" in updates and updates["artifact_id"] is not None:
        if not db.query(Artifact).filter(Artifact.id == updates["artifact_id"]).first():
            raise HTTPException(status_code=400, detail="Artifact not found")

    # Version bump when steps or description change
    version_fields = {"steps", "description"}
    if version_fields & updates.keys():
        updates["version"] = protocol.version + 1

    for field, value in updates.items():
        setattr(protocol, field, value)

    db.commit()
    db.refresh(protocol)

    # Eager-load for detail response
    protocol = (
        db.query(Protocol)
        .options(
            joinedload(Protocol.tags),
            joinedload(Protocol.artifact),
        )
        .filter(Protocol.id == protocol_id)
        .first()
    )
    return protocol


@router.delete("/{protocol_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_protocol(protocol_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a protocol."""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    db.delete(protocol)
    db.commit()


# ---------------------------------------------------------------------------
# Protocol-Tag attachment — /api/protocols/{protocol_id}/tags
# ---------------------------------------------------------------------------


@protocol_tags_router.get("/{protocol_id}/tags", response_model=list[TagResponse])
def list_tags_on_protocol(
    protocol_id: UUID, db: Session = Depends(get_db)
) -> list[Tag]:
    """List all tags attached to a protocol."""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return protocol.tags


@protocol_tags_router.post(
    "/{protocol_id}/tags/{tag_id}", response_model=TagResponse,
)
def attach_tag_to_protocol(
    protocol_id: UUID, tag_id: UUID, db: Session = Depends(get_db)
) -> Tag:
    """Attach a tag to a protocol. Idempotent."""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    existing = (
        db.query(ProtocolTag)
        .filter(ProtocolTag.protocol_id == protocol_id, ProtocolTag.tag_id == tag_id)
        .first()
    )
    if not existing:
        db.add(ProtocolTag(protocol_id=protocol_id, tag_id=tag_id))
        db.commit()

    return tag


@protocol_tags_router.delete(
    "/{protocol_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT,
)
def detach_tag_from_protocol(
    protocol_id: UUID, tag_id: UUID, db: Session = Depends(get_db)
) -> None:
    """Remove a tag from a protocol."""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    link = (
        db.query(ProtocolTag)
        .filter(ProtocolTag.protocol_id == protocol_id, ProtocolTag.tag_id == tag_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Tag is not attached to this protocol")
    db.delete(link)
    db.commit()
