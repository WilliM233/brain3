"""BRAIN 3.0 — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import SessionLocal
from app.routers import activity, checkins, domains, goals, projects, routines, tags, tasks

app = FastAPI(
    title="BRAIN 3.0",
    description="AI-powered personal operating system for ADHD — Phase 1 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(tags.task_tags_router, prefix="/api/tasks", tags=["Task Tags"])
