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

"""CRUD endpoints for Tasks."""

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Project, Task
from app.schemas.batch import BatchTaskCreate, BatchTaskCreateResponse
from app.schemas.tasks import (
    TaskCreate,
    TaskDetailResponse,
    TaskResponse,
    TaskUpdate,
)

router = APIRouter()


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> Task:
    """Create a new task. Validates project_id if provided."""
    if payload.project_id is not None:
        project = db.query(Project).filter(Project.id == payload.project_id).first()
        if not project:
            raise HTTPException(status_code=400, detail="Project not found")

    task = Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/batch", response_model=BatchTaskCreateResponse, status_code=status.HTTP_201_CREATED)
def batch_create_tasks(
    payload: BatchTaskCreate, db: Session = Depends(get_db)
) -> dict:
    """Batch create tasks. Atomic — all succeed or all fail."""
    created = []
    for idx, item in enumerate(payload.items):
        if item.project_id is not None:
            project = db.query(Project).filter(Project.id == item.project_id).first()
            if not project:
                raise HTTPException(
                    status_code=400,
                    detail=f"Batch item {idx}: Project not found (project_id: {item.project_id})",
                )

        task = Task(**item.model_dump())
        db.add(task)
        created.append(task)

    db.flush()
    db.commit()
    for task in created:
        db.refresh(task)
    return {"created": created, "count": len(created)}


@router.get("/", response_model=list[TaskResponse])
def list_tasks(
    project_id: UUID | None = Query(None),
    standalone: bool | None = Query(None),
    task_status: str | None = Query(None, alias="status"),
    cognitive_type: str | None = Query(None),
    energy_cost_min: int | None = Query(None),
    energy_cost_max: int | None = Query(None),
    friction_min: int | None = Query(None),
    friction_max: int | None = Query(None),
    context_required: str | None = Query(None),
    due_before: date | None = Query(None),
    due_after: date | None = Query(None),
    overdue: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> list[Task]:
    """List tasks with composable filters."""
    query = db.query(Task)

    if project_id is not None:
        query = query.filter(Task.project_id == project_id)
    if standalone is True:
        query = query.filter(Task.project_id.is_(None))
    if task_status is not None:
        query = query.filter(Task.status == task_status)
    if cognitive_type is not None:
        query = query.filter(Task.cognitive_type == cognitive_type)
    if energy_cost_min is not None:
        query = query.filter(Task.energy_cost >= energy_cost_min)
    if energy_cost_max is not None:
        query = query.filter(Task.energy_cost <= energy_cost_max)
    if friction_min is not None:
        query = query.filter(Task.activation_friction >= friction_min)
    if friction_max is not None:
        query = query.filter(Task.activation_friction <= friction_max)
    if context_required is not None:
        query = query.filter(Task.context_required == context_required)
    if due_before is not None:
        query = query.filter(Task.due_date <= due_before)
    if due_after is not None:
        query = query.filter(Task.due_date >= due_after)
    if overdue is True:
        query = query.filter(
            Task.due_date < date.today(),
            Task.status.notin_(["completed", "skipped"]),
        )

    return query.order_by(Task.created_at).all()


@router.get("/{task_id}", response_model=TaskDetailResponse)
def get_task(task_id: UUID, db: Session = Depends(get_db)) -> Task:
    """Get a single task with its nested tags."""
    task = (
        db.query(Task)
        .options(joinedload(Task.tags))
        .filter(Task.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: UUID, payload: TaskUpdate, db: Session = Depends(get_db)
) -> Task:
    """Partial update of a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    # Auto-manage completed_at based on status transitions
    if task.status == "completed" and task.completed_at is None:
        task.completed_at = datetime.now(tz=timezone.utc)
    elif task.status != "completed" and task.completed_at is not None:
        task.completed_at = None

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
