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

from app.auth import install_app_bearer_auth
from app.config import settings
from app.database import SessionLocal
from app.routers import (
    activity,
    artifacts,
    checkins,
    directives,
    domains,
    goals,
    graduation,
    habits,
    notification,
    projects,
    protocols,
    reports,
    routines,
    rules,
    skills,
    tags,
    tasks,
)
from app.services.delivery_promoter import install_delivery_promoter

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

# Bearer auth on /api/app/*. Skipped with a warning when the token is unset
# (dev convenience) — production must set BRAIN3_APP_BEARER_TOKEN.
install_app_bearer_auth(app, settings.APP_BEARER_TOKEN)

# Delivery promoter ([2C-05a]) — asyncio task that polls notification_queue
# and transitions due rows from pending → delivered. Stream D will expand
# this into full scheduler infrastructure.
install_delivery_promoter(app)


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


@app.get("/api/app/health")
def app_health_check() -> dict:
    """Authed probe endpoint for the companion app's validation ping.

    Sits behind ``AppBearerAuthMiddleware``. The companion app calls this
    during URL+token pairing to confirm both that the server is reachable
    and that the bearer token is valid.
    """
    return {"ok": True}


app.include_router(domains.router, prefix="/api/domains", tags=["Domains"])
app.include_router(goals.router, prefix="/api/goals", tags=["Goals"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(tags.router, prefix="/api/tags", tags=["Tags"])
app.include_router(routines.router, prefix="/api/routines", tags=["Routines"])
app.include_router(habits.router, prefix="/api/habits", tags=["Habits"])
app.include_router(checkins.router, prefix="/api/checkins", tags=["Check-ins"])
app.include_router(activity.router, prefix="/api/activity", tags=["Activity Log"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(tags.task_tags_router, prefix="/api/tasks", tags=["Task Tags"])
app.include_router(
    activity.activity_tags_router, prefix="/api/activity", tags=["Activity Tags"],
)
app.include_router(artifacts.router, prefix="/api/artifacts", tags=["Artifacts"])
app.include_router(
    artifacts.artifact_tags_router, prefix="/api/artifacts", tags=["Artifact Tags"],
)
app.include_router(protocols.router, prefix="/api/protocols", tags=["Protocols"])
app.include_router(
    protocols.protocol_tags_router, prefix="/api/protocols", tags=["Protocol Tags"],
)
app.include_router(directives.router, prefix="/api/directives", tags=["Directives"])
app.include_router(
    directives.directive_tags_router, prefix="/api/directives", tags=["Directive Tags"],
)
app.include_router(skills.router, prefix="/api/skills", tags=["Skills"])
app.include_router(
    notification.router, prefix="/api/notifications", tags=["Notifications"],
)
app.include_router(rules.router, prefix="/api/rules", tags=["Rules"])
app.include_router(
    graduation.habit_graduation_router, prefix="/api/habits", tags=["Graduation"],
)
app.include_router(
    graduation.graduation_router, prefix="/api/graduation", tags=["Graduation"],
)
app.include_router(
    skills.skill_domains_router, prefix="/api/skills", tags=["Skill Domains"],
)
app.include_router(
    skills.skill_protocols_router, prefix="/api/skills", tags=["Skill Protocols"],
)
app.include_router(
    skills.skill_directives_router, prefix="/api/skills", tags=["Skill Directives"],
)
