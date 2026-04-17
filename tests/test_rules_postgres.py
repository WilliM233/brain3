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

"""Postgres-backed integration tests for the Rules API.

The in-memory SQLite harness (``tests/conftest.py``) synthesizes the schema
from ``Base.metadata`` and cannot observe defects that live in Alembic
migrations or in the disagreement between the ORM binding and a native
Postgres enum type. This module exercises ``create_rule`` end-to-end
against a real Postgres instance migrated via Alembic — the only path
that reproduces ``[2F-Bug-02]``.

The module is skipped when no Postgres is reachable so the default
``pytest -v`` run stays green on machines without Docker. Set
``BRAIN3_TEST_POSTGRES_URL`` to override the server connection (for CI
or non-default credentials). The test DB itself is created, migrated,
and dropped per session.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from alembic import config as alembic_config
from app.config import settings
from app.database import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Connection — server-level URL (for CREATE/DROP DATABASE) and per-test DB
# ---------------------------------------------------------------------------

_TEST_DB_NAME = "brain3_test_ruleoperator"


def _pg_host() -> str:
    """Host to reach Postgres from the test runner.

    Settings defaults ``POSTGRES_HOST`` to ``db`` (the compose service name)
    so the API container can resolve it. Tests run on the host machine and
    need ``localhost``. Honour an override so CI can point elsewhere.
    """
    return os.environ.get("BRAIN3_TEST_POSTGRES_HOST", "localhost")


def _server_url() -> str:
    """URL for the Postgres server's default ``postgres`` database."""
    return (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{_pg_host()}:{settings.POSTGRES_PORT}/postgres"
    )


def _test_db_url() -> str:
    base = _server_url().rsplit("/", 1)[0]
    return f"{base}/{_TEST_DB_NAME}"


def _postgres_available() -> bool:
    try:
        engine = create_engine(_server_url(), isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="Postgres not reachable — set BRAIN3_TEST_POSTGRES_URL or start brain3-dev",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pg_engine() -> Generator[Engine, None, None]:
    """Create a fresh test DB, run Alembic migrations against it, tear down."""
    # The autouse setup_database fixture in tests/conftest.py calls
    # Base.metadata.create_all against the SQLite engine for every test. That
    # is harmless here — we build an independent Postgres engine and override
    # get_db per test.
    server = create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        conn.execute(
            text(f"DROP DATABASE IF EXISTS {_TEST_DB_NAME} WITH (FORCE)"),
        )
        conn.execute(text(f"CREATE DATABASE {_TEST_DB_NAME}"))

    # alembic/env.py re-reads settings.database_url on every invocation, so we
    # point settings at the test DB before command.upgrade runs and restore
    # the originals after. Mutating settings in-place is safe: no live app
    # code path is bound to this module's lifecycle.
    saved = (settings.POSTGRES_HOST, settings.POSTGRES_DB)
    settings.POSTGRES_HOST = _pg_host()
    settings.POSTGRES_DB = _TEST_DB_NAME
    try:
        alembic_cfg = alembic_config.Config(str(_repo_root() / "alembic.ini"))
        alembic_cfg.set_main_option(
            "script_location", str(_repo_root() / "alembic"),
        )
        command.upgrade(alembic_cfg, "head")
    finally:
        settings.POSTGRES_HOST, settings.POSTGRES_DB = saved

    engine = create_engine(_test_db_url())
    try:
        yield engine
    finally:
        engine.dispose()
        with server.connect() as conn:
            conn.execute(
                text(f"DROP DATABASE IF EXISTS {_TEST_DB_NAME} WITH (FORCE)"),
            )
        server.dispose()


@pytest.fixture
def pg_client(pg_engine: Engine) -> Generator[TestClient, None, None]:
    """TestClient bound to the Postgres test DB via a get_db override."""
    TestingSession = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    def _override_get_db() -> Generator[Session, None, None]:
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _clean_rules(pg_engine: Engine) -> Generator[None, None, None]:
    """Truncate rules between tests so each starts from a known state."""
    with pg_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE rules RESTART IDENTITY CASCADE"))
    yield


def _repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_BASE_PAYLOAD = {
    "name": "Postgres round-trip",
    "entity_type": "habit",
    "metric": "consecutive_skips",
    "threshold": 3,
    "notification_type": "pattern_observation",
    "message_template": "{entity_name} skipped {metric_value} times",
}


@pytest.mark.parametrize("operator", [">=", "<=", "=="])
def test_create_rule_round_trips_operator_on_postgres(
    pg_client: TestClient, operator: str,
) -> None:
    """create_rule must succeed and return the original operator symbol.

    Before [2F-Bug-02]'s fix the ORM wrote ``'gte'`` while the Postgres enum
    only accepted ``'>='`` — this assertion regresses to a 500 on every
    operator value.
    """
    payload = {**_BASE_PAYLOAD, "operator": operator}

    resp = pg_client.post("/api/rules/", json=payload)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["operator"] == operator
    rule_id = body["id"]

    # Explicit read-back confirms the value survives a second round trip
    # through hydration (enum name in DB → enum value on the wire).
    get_resp = pg_client.get(f"/api/rules/{rule_id}")
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["operator"] == operator


def test_ruleoperator_enum_labels_are_wordform(pg_engine: Engine) -> None:
    """The Postgres enum type must carry word-form labels after migration 018."""
    with pg_engine.connect() as conn:
        labels = conn.execute(
            text(
                "SELECT enumlabel FROM pg_enum "
                "JOIN pg_type ON pg_type.oid = pg_enum.enumtypid "
                "WHERE pg_type.typname = 'ruleoperator' "
                "ORDER BY enumsortorder",
            ),
        ).scalars().all()

    assert labels == ["gte", "lte", "eq"]
