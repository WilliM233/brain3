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

"""CRUD and evaluation endpoints for Rules."""

from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Rule
from app.schemas.rule import (
    NotificationType,
    RuleCreate,
    RuleEntityType,
    RuleEvaluationResultResponse,
    RuleRead,
    RuleUpdate,
)
from app.services.rule_evaluation import evaluate_rules

router = APIRouter()


# ---------------------------------------------------------------------------
# POST — create rule
# ---------------------------------------------------------------------------

@router.post("/", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: RuleCreate, db: Session = Depends(get_db),
) -> Rule:
    """Create a rule. Template placeholders are validated by the schema."""
    rule = Rule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


# ---------------------------------------------------------------------------
# GET list — with composable filters
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[RuleRead])
def list_rules(
    entity_type: RuleEntityType | None = Query(None),
    enabled: bool | None = Query(None),
    notification_type: NotificationType | None = Query(None),
    entity_id: UUID | None = Query(None),
    is_default: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> list[Rule]:
    """List rules with composable filters (AND logic)."""
    query = db.query(Rule)

    if entity_type is not None:
        query = query.filter(Rule.entity_type == entity_type)
    if enabled is not None:
        query = query.filter(Rule.enabled == enabled)
    if notification_type is not None:
        query = query.filter(Rule.notification_type == notification_type)
    if entity_id is not None:
        query = query.filter(Rule.entity_id == entity_id)
    if is_default is not None:
        query = query.filter(Rule.is_default == is_default)

    return query.order_by(Rule.created_at.desc()).all()


# ---------------------------------------------------------------------------
# POST — evaluate all rules
# ---------------------------------------------------------------------------

@router.post("/evaluate", response_model=list[RuleEvaluationResultResponse])
def evaluate_all_rules(
    db: Session = Depends(get_db),
) -> list[dict]:
    """Evaluate all enabled rules and create notifications for matches."""
    results = evaluate_rules(db)
    return [asdict(r) for r in results]


# ---------------------------------------------------------------------------
# POST — evaluate single rule
# ---------------------------------------------------------------------------

@router.post("/{rule_id}/evaluate", response_model=RuleEvaluationResultResponse)
def evaluate_single_rule(
    rule_id: UUID,
    respect_cooldown: bool = Query(True),
    db: Session = Depends(get_db),
) -> dict:
    """Evaluate a single rule, optionally ignoring cooldown for testing."""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    results = evaluate_rules(db, rule_id=rule_id, respect_cooldown=respect_cooldown)
    return asdict(results[0])


# ---------------------------------------------------------------------------
# GET detail
# ---------------------------------------------------------------------------

@router.get("/{rule_id}", response_model=RuleRead)
def get_rule(rule_id: UUID, db: Session = Depends(get_db)) -> Rule:
    """Get a single rule by ID."""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


# ---------------------------------------------------------------------------
# PATCH — partial update
# ---------------------------------------------------------------------------

@router.patch("/{rule_id}", response_model=RuleRead)
def update_rule(
    rule_id: UUID, payload: RuleUpdate, db: Session = Depends(get_db),
) -> Rule:
    """Partial update of a rule. Re-validates template if changed."""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a rule. FK cascade sets notification_queue.rule_id to NULL."""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.delete(rule)
    db.commit()
