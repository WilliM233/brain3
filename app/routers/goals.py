"""CRUD endpoints for Goals."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Domain, Goal
from app.schemas.goals import (
    GoalCreate,
    GoalDetailResponse,
    GoalResponse,
    GoalUpdate,
)

router = APIRouter()


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db)) -> Goal:
    """Create a new goal. Validates that domain_id references an existing domain."""
    domain = db.query(Domain).filter(Domain.id == payload.domain_id).first()
    if not domain:
        raise HTTPException(status_code=400, detail="Domain not found")

    goal = Goal(**payload.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/", response_model=list[GoalResponse])
def list_goals(
    domain_id: UUID | None = Query(None),
    goal_status: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> list[Goal]:
    """List goals with optional filters for domain_id and status."""
    query = db.query(Goal)

    if domain_id is not None:
        query = query.filter(Goal.domain_id == domain_id)
    if goal_status is not None:
        query = query.filter(Goal.status == goal_status)

    return query.order_by(Goal.created_at).all()


@router.get("/{goal_id}", response_model=GoalDetailResponse)
def get_goal(goal_id: UUID, db: Session = Depends(get_db)) -> Goal:
    """Get a single goal with its nested projects."""
    goal = (
        db.query(Goal)
        .options(joinedload(Goal.projects))
        .filter(Goal.id == goal_id)
        .first()
    )
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: UUID, payload: GoalUpdate, db: Session = Depends(get_db)
) -> Goal:
    """Partial update of a goal."""
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)

    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a goal."""
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    db.delete(goal)
    db.commit()
