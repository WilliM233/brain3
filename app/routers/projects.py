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

"""CRUD endpoints for Projects."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Goal, Project
from app.schemas.projects import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter()


def _compute_progress(project: Project) -> None:
    """Set progress_pct from the ratio of completed tasks to total tasks."""
    tasks = project.tasks
    if not tasks:
        project.progress_pct = 0
    else:
        completed = sum(1 for t in tasks if t.status == "completed")
        project.progress_pct = round(completed * 100 / len(tasks))


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    """Create a new project. Validates that goal_id references an existing goal."""
    goal = db.query(Goal).filter(Goal.id == payload.goal_id).first()
    if not goal:
        raise HTTPException(status_code=400, detail="Goal not found")

    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/", response_model=list[ProjectResponse])
def list_projects(
    goal_id: UUID | None = Query(None),
    project_status: str | None = Query(None, alias="status"),
    has_deadline: bool | None = Query(None),
    overdue: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> list[Project]:
    """List projects with optional filters."""
    query = db.query(Project).options(joinedload(Project.tasks))

    if goal_id is not None:
        query = query.filter(Project.goal_id == goal_id)
    if project_status is not None:
        query = query.filter(Project.status == project_status)
    if has_deadline is True:
        query = query.filter(Project.deadline.isnot(None))
    if overdue is True:
        query = query.filter(
            Project.deadline < date.today(),
            Project.status.notin_(["completed", "abandoned"]),
        )

    projects = query.order_by(Project.created_at).all()
    for project in projects:
        _compute_progress(project)
    return projects


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(project_id: UUID, db: Session = Depends(get_db)) -> Project:
    """Get a single project with its nested tasks."""
    project = (
        db.query(Project)
        .options(joinedload(Project.tasks))
        .filter(Project.id == project_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _compute_progress(project)
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID, payload: ProjectUpdate, db: Session = Depends(get_db)
) -> Project:
    """Partial update of a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    _compute_progress(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a project and cascade to its tasks."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
