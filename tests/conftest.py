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


FAKE_UUID = str(uuid.uuid4())
