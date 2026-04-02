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

"""BRAIN 3.0 — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.routers import (
    activity,
    checkins,
    domains,
    goals,
    projects,
    reports,
    routines,
    tags,
    tasks,
)

app = FastAPI(
    title="BRAIN 3.0",
    description="AI-powered personal operating system for ADHD — Phase 1 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict:
    """Check API and database connectivity."""
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return {"status": "healthy", "database": "connected"}
        finally:
            db.close()
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected"},
        )


app.include_router(domains.router, prefix="/api/domains", tags=["Domains"])
app.include_router(goals.router, prefix="/api/goals", tags=["Goals"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(tags.router, prefix="/api/tags", tags=["Tags"])
app.include_router(routines.router, prefix="/api/routines", tags=["Routines"])
app.include_router(checkins.router, prefix="/api/checkins", tags=["Check-ins"])
app.include_router(activity.router, prefix="/api/activity", tags=["Activity Log"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(tags.task_tags_router, prefix="/api/tasks", tags=["Task Tags"])
app.include_router(
    activity.activity_tags_router, prefix="/api/activity", tags=["Activity Tags"],
)
