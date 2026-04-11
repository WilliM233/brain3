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

"""CRUD endpoints for Directives."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Directive, DirectiveTag, Tag
from app.schemas.batch import BatchDirectiveCreate, BatchDirectiveCreateResponse
from app.schemas.directives import (
    DirectiveCreate,
    DirectiveResolveResponse,
    DirectiveResponse,
    DirectiveUpdate,
)
from app.schemas.tags import TagResponse

router = APIRouter()
directive_tags_router = APIRouter()


# ---------------------------------------------------------------------------
# Resolve — must be registered BEFORE /{id} to avoid path conflict
# ---------------------------------------------------------------------------


@router.get("/resolve", response_model=DirectiveResolveResponse)
def resolve_directives(
    skill_id: UUID | None = Query(
        None, description="Include skill-scoped directives for this skill",
    ),
    scope_ref: UUID | None = Query(
        None, description="Include agent-scoped directives for this agent project",
    ),
    db: Session = Depends(get_db),
) -> dict:
    """Merge directives by scope — global + optional skill + optional agent."""
    global_directives = (
        db.query(Directive)
        .filter(Directive.scope == "global")
        .order_by(Directive.priority.desc())
        .all()
    )

    skill_directives = []
    if skill_id is not None:
        skill_directives = (
            db.query(Directive)
            .filter(Directive.scope == "skill", Directive.scope_ref == skill_id)
            .order_by(Directive.priority.desc())
            .all()
        )

    agent_directives = []
    if scope_ref is not None:
        agent_directives = (
            db.query(Directive)
            .filter(Directive.scope == "agent", Directive.scope_ref == scope_ref)
            .order_by(Directive.priority.desc())
            .all()
        )

    return {
        "global_directives": global_directives,
        "skill_directives": skill_directives,
        "agent_directives": agent_directives,
    }


# ---------------------------------------------------------------------------
# Directive CRUD — /api/directives
# ---------------------------------------------------------------------------


@router.post(
    "/batch", response_model=BatchDirectiveCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def batch_create_directives(
    payload: BatchDirectiveCreate, db: Session = Depends(get_db)
) -> dict:
    """Batch create directives. Atomic — all succeed or all fail."""
    created = []
    try:
        for idx, item in enumerate(payload.items):
            tags = []
            if item.tag_ids:
                for tid in item.tag_ids:
                    tag = db.query(Tag).filter(Tag.id == tid).first()
                    if not tag:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Batch item {idx}: Tag {tid} not found",
                        )
                    tags.append(tag)

            directive = Directive(
                **item.model_dump(exclude={"tag_ids"}),
            )
            db.add(directive)
            db.flush()

            for tag in tags:
                db.add(DirectiveTag(directive_id=directive.id, tag_id=tag.id))

            created.append(directive)
    except HTTPException:
        db.rollback()
        raise

    db.commit()
    for directive in created:
        db.refresh(directive)
    return {"created": created, "count": len(created)}


@router.post("/", response_model=DirectiveResponse, status_code=status.HTTP_201_CREATED)
def create_directive(payload: DirectiveCreate, db: Session = Depends(get_db)) -> Directive:
    """Create a new directive. Validates tag_ids if provided."""
    tags = []
    if payload.tag_ids:
        for tid in payload.tag_ids:
            tag = db.query(Tag).filter(Tag.id == tid).first()
            if not tag:
                raise HTTPException(status_code=400, detail=f"Tag {tid} not found")
            tags.append(tag)

    directive = Directive(
        **payload.model_dump(exclude={"tag_ids"}),
    )
    db.add(directive)
    db.flush()

    for tag in tags:
        db.add(DirectiveTag(directive_id=directive.id, tag_id=tag.id))

    db.commit()
    db.refresh(directive)
    return directive


@router.get("/", response_model=list[DirectiveResponse])
def list_directives(
    scope: str | None = Query(None, description="Filter by scope enum"),
    scope_ref: UUID | None = Query(None, description="Filter by scope reference"),
    is_seedable: bool | None = Query(None),
    priority_min: int | None = Query(None, ge=1, le=10, description="Minimum priority (inclusive)"),
    priority_max: int | None = Query(None, ge=1, le=10, description="Maximum priority (inclusive)"),
    search: str | None = Query(None, description="Case-insensitive name search"),
    tag: str | None = Query(None, description="Comma-separated tag names (AND logic)"),
    db: Session = Depends(get_db),
) -> list[Directive]:
    """List directives with composable filters."""
    query = db.query(Directive)

    if scope is not None:
        query = query.filter(Directive.scope == scope)
    if scope_ref is not None:
        query = query.filter(Directive.scope_ref == scope_ref)
    if is_seedable is not None:
        query = query.filter(Directive.is_seedable == is_seedable)
    if priority_min is not None:
        query = query.filter(Directive.priority >= priority_min)
    if priority_max is not None:
        query = query.filter(Directive.priority <= priority_max)
    if search is not None:
        query = query.filter(Directive.name.ilike(f"%{search}%"))
    if tag is not None:
        tag_names = [t.strip().lower() for t in tag.split(",") if t.strip()]
        for tag_name in tag_names:
            query = query.filter(
                Directive.tags.any(Tag.name == tag_name)
            )

    return query.order_by(Directive.created_at.desc()).all()


@router.get("/{directive_id}", response_model=DirectiveResponse)
def get_directive(directive_id: UUID, db: Session = Depends(get_db)) -> Directive:
    """Get a single directive by ID."""
    directive = db.query(Directive).filter(Directive.id == directive_id).first()
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")
    return directive


@router.patch("/{directive_id}", response_model=DirectiveResponse)
def update_directive(
    directive_id: UUID, payload: DirectiveUpdate, db: Session = Depends(get_db)
) -> Directive:
    """Partial update with post-merge scope/scope_ref cross-validation."""
    directive = db.query(Directive).filter(Directive.id == directive_id).first()
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(directive, field, value)

    # Validate scope/scope_ref on post-merge state
    if directive.scope == "global" and directive.scope_ref is not None:
        raise HTTPException(
            status_code=422,
            detail="scope_ref must be null for global directives",
        )
    if directive.scope in ("skill", "agent") and directive.scope_ref is None:
        raise HTTPException(
            status_code=422,
            detail="scope_ref is required for skill and agent directives",
        )

    db.commit()
    db.refresh(directive)
    return directive


@router.delete("/{directive_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_directive(directive_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a directive."""
    directive = db.query(Directive).filter(Directive.id == directive_id).first()
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")
    db.delete(directive)
    db.commit()


# ---------------------------------------------------------------------------
# Directive-Tag attachment — /api/directives/{directive_id}/tags
# ---------------------------------------------------------------------------


@directive_tags_router.get("/{directive_id}/tags", response_model=list[TagResponse])
def list_tags_on_directive(
    directive_id: UUID, db: Session = Depends(get_db)
) -> list[Tag]:
    """List all tags attached to a directive."""
    directive = db.query(Directive).filter(Directive.id == directive_id).first()
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")
    return directive.tags


@directive_tags_router.post(
    "/{directive_id}/tags/{tag_id}", response_model=TagResponse,
)
def attach_tag_to_directive(
    directive_id: UUID, tag_id: UUID, db: Session = Depends(get_db)
) -> Tag:
    """Attach a tag to a directive. Idempotent."""
    directive = db.query(Directive).filter(Directive.id == directive_id).first()
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    existing = (
        db.query(DirectiveTag)
        .filter(DirectiveTag.directive_id == directive_id, DirectiveTag.tag_id == tag_id)
        .first()
    )
    if not existing:
        db.add(DirectiveTag(directive_id=directive_id, tag_id=tag_id))
        db.commit()

    return tag


@directive_tags_router.delete(
    "/{directive_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT,
)
def detach_tag_from_directive(
    directive_id: UUID, tag_id: UUID, db: Session = Depends(get_db)
) -> None:
    """Remove a tag from a directive."""
    directive = db.query(Directive).filter(Directive.id == directive_id).first()
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    link = (
        db.query(DirectiveTag)
        .filter(DirectiveTag.directive_id == directive_id, DirectiveTag.tag_id == tag_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Tag is not attached to this directive")
    db.delete(link)
    db.commit()
