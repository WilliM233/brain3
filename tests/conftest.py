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

"""Shared test fixtures — in-memory SQLite database and FastAPI test client."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register all models with Base
from app.database import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# SQLite in-memory engine with UUID support
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _enable_fk(dbapi_conn, connection_record):
    """Enable foreign-key enforcement in SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Yield a database session for direct ORM use in tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """FastAPI TestClient with the test database session injected."""

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_domain(client: TestClient, **overrides) -> dict:
    """Create a domain via the API and return the response JSON."""
    data = {"name": "Test Domain", **overrides}
    resp = client.post("/api/domains", json=data)
    assert resp.status_code == 201
    return resp.json()


def make_goal(client: TestClient, domain_id: str, **overrides) -> dict:
    """Create a goal via the API and return the response JSON."""
    data = {"domain_id": domain_id, "title": "Test Goal", **overrides}
    resp = client.post("/api/goals", json=data)
    assert resp.status_code == 201
    return resp.json()


def make_project(client: TestClient, goal_id: str, **overrides) -> dict:
    """Create a project via the API and return the response JSON."""
    data = {"goal_id": goal_id, "title": "Test Project", **overrides}
    resp = client.post("/api/projects", json=data)
    assert resp.status_code == 201
    return resp.json()


def make_task(client: TestClient, **overrides) -> dict:
    """Create a task via the API and return the response JSON."""
    data = {"title": "Test Task", **overrides}
    resp = client.post("/api/tasks", json=data)
    assert resp.status_code == 201
    return resp.json()


def make_routine(client: TestClient, domain_id: str, **overrides) -> dict:
    """Create a routine via the API and return the response JSON."""
    data = {
        "domain_id": domain_id,
        "title": "Test Routine",
        "frequency": "daily",
        **overrides,
    }
    resp = client.post("/api/routines", json=data)
    assert resp.status_code == 201
    return resp.json()


def make_tag(client: TestClient, **overrides) -> dict:
    """Create a tag via the API and return the response JSON."""
    data = {"name": "test-tag", **overrides}
    resp = client.post("/api/tags", json=data)
    assert resp.status_code in (200, 201)
    return resp.json()


def make_activity(client: TestClient, **overrides) -> dict:
    """Create an activity log entry via the API and return the response JSON."""
    data = {"action_type": "completed", **overrides}
    resp = client.post("/api/activity", json=data)
    assert resp.status_code == 201
    return resp.json()


def make_checkin(client: TestClient, **overrides) -> dict:
    """Create a check-in via the API and return the response JSON."""
    data = {"checkin_type": "morning", **overrides}
    resp = client.post("/api/checkins", json=data)
    assert resp.status_code == 201
    return resp.json()


FAKE_UUID = str(uuid.uuid4())
