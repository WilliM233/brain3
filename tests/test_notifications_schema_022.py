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

"""Postgres-backed migration tests for ``022_add_scheduled_date_to_notifications``.

The in-memory SQLite harness in ``tests/conftest.py`` builds the schema from
``Base.metadata`` and never invokes Alembic, which means it cannot exercise
the ``UPDATE notification_queue SET scheduled_date = scheduled_at::date``
backfill (Postgres-specific cast). This module migrates from revision 021
to 022 against a real Postgres, seeds rows that look like pre-migration
data (``scheduled_date IS NULL`` after the column is added, but before
backfill), and verifies the backfill + the resulting NOT NULL constraint.

Skipped when no Postgres is reachable so ``pytest -v`` stays green on
machines without Docker.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from alembic import command
from alembic import config as alembic_config
from app.config import settings

# ---------------------------------------------------------------------------
# Connection plumbing — mirrors test_rules_postgres.py
# ---------------------------------------------------------------------------

_TEST_DB_NAME = "brain3_test_scheduled_date"


def _pg_host() -> str:
    return os.environ.get("BRAIN3_TEST_POSTGRES_HOST", "localhost")


def _server_url() -> str:
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
    reason="Postgres not reachable — set BRAIN3_TEST_POSTGRES_HOST or start brain3-dev",
)


def _repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent


def _alembic_cfg() -> alembic_config.Config:
    cfg = alembic_config.Config(str(_repo_root() / "alembic.ini"))
    cfg.set_main_option("script_location", str(_repo_root() / "alembic"))
    return cfg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pg_engine_at_021() -> Generator[Engine, None, None]:
    """Fresh test DB migrated to revision 021 (one before the change)."""
    server = create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {_TEST_DB_NAME} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {_TEST_DB_NAME}"))

    saved = (settings.POSTGRES_HOST, settings.POSTGRES_DB)
    settings.POSTGRES_HOST = _pg_host()
    settings.POSTGRES_DB = _TEST_DB_NAME
    try:
        command.upgrade(_alembic_cfg(), "21a1b2c3d4e5")
    finally:
        settings.POSTGRES_HOST, settings.POSTGRES_DB = saved

    engine = create_engine(_test_db_url())
    try:
        yield engine
    finally:
        engine.dispose()
        with server.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {_TEST_DB_NAME} WITH (FORCE)"))
        server.dispose()


def _upgrade_to_022() -> None:
    saved = (settings.POSTGRES_HOST, settings.POSTGRES_DB)
    settings.POSTGRES_HOST = _pg_host()
    settings.POSTGRES_DB = _TEST_DB_NAME
    try:
        command.upgrade(_alembic_cfg(), "22a1b2c3d4e5")
    finally:
        settings.POSTGRES_HOST, settings.POSTGRES_DB = saved


def _insert_legacy_notification(
    engine: Engine, scheduled_at: datetime,
) -> uuid.UUID:
    """Insert a row using the pre-022 schema (no scheduled_date column yet)."""
    nid = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO notification_queue (
                    id, notification_type, delivery_type, status,
                    scheduled_at, target_entity_type, target_entity_id,
                    message, scheduled_by
                ) VALUES (
                    :id, 'habit_nudge', 'notification', 'pending',
                    :sa, 'habit', :tid, 'legacy row', 'system'
                )
                """
            ),
            {"id": nid, "sa": scheduled_at, "tid": uuid.uuid4()},
        )
    return nid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMigration022Backfill:
    """``scheduled_date`` is backfilled from ``scheduled_at::date`` for
    existing rows when migration 022 runs."""

    def test_backfill_populates_scheduled_date_from_scheduled_at(
        self, pg_engine_at_021: Engine,
    ) -> None:
        engine = pg_engine_at_021

        morning = datetime(2026, 4, 15, 9, 30, tzinfo=UTC)
        evening = datetime(2026, 4, 16, 23, 45, tzinfo=UTC)
        nid_morning = _insert_legacy_notification(engine, morning)
        nid_evening = _insert_legacy_notification(engine, evening)

        _upgrade_to_022()

        with engine.connect() as conn:
            row_m = conn.execute(
                text(
                    "SELECT scheduled_date FROM notification_queue WHERE id = :id",
                ),
                {"id": nid_morning},
            ).scalar_one()
            row_e = conn.execute(
                text(
                    "SELECT scheduled_date FROM notification_queue WHERE id = :id",
                ),
                {"id": nid_evening},
            ).scalar_one()

        assert row_m == date(2026, 4, 15)
        assert row_e == date(2026, 4, 16)

    def test_post_migration_insert_without_scheduled_date_fails(
        self, pg_engine_at_021: Engine,
    ) -> None:
        """After 022, scheduled_date is NOT NULL — raw INSERT without it fails."""
        engine = pg_engine_at_021
        _upgrade_to_022()

        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO notification_queue (
                            id, notification_type, delivery_type, status,
                            scheduled_at, target_entity_type, target_entity_id,
                            message, scheduled_by
                        ) VALUES (
                            :id, 'habit_nudge', 'notification', 'pending',
                            :sa, 'habit', :tid, 'should fail', 'system'
                        )
                        """
                    ),
                    {
                        "id": uuid.uuid4(),
                        "sa": datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
                        "tid": uuid.uuid4(),
                    },
                )

    def test_index_on_scheduled_date_exists(
        self, pg_engine_at_021: Engine,
    ) -> None:
        """``ix_nq_scheduled_date`` is present after migration 022."""
        engine = pg_engine_at_021
        _upgrade_to_022()

        with engine.connect() as conn:
            indexes = conn.execute(
                text(
                    """
                    SELECT indexname FROM pg_indexes
                    WHERE tablename = 'notification_queue'
                    """,
                ),
            ).scalars().all()

        assert "ix_nq_scheduled_date" in indexes
