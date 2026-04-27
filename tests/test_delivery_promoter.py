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

"""Tests for the [2C-05a] lightweight delivery promoter."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import NotificationQueue
from app.services import delivery_promoter
from app.services.delivery_promoter import (
    _run_poller,
    _tick,
    install_delivery_promoter,
    promote_due_notifications,
)
from tests.conftest import TestingSessionLocal


def _make_pending(
    db,
    *,
    scheduled_at: datetime,
    notification_type: str = "habit_nudge",
) -> NotificationQueue:
    """Insert a notification_queue row directly via the ORM and return it."""
    row = NotificationQueue(
        notification_type=notification_type,
        delivery_type="notification",
        status="pending",
        scheduled_at=scheduled_at,
        scheduled_date=scheduled_at.date(),
        target_entity_type="habit",
        target_entity_id=uuid.uuid4(),
        message="Time to stretch!",
        scheduled_by="system",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# promote_due_notifications — happy paths and skips
# ---------------------------------------------------------------------------


class TestPromoteDueNotifications:
    """Direct tests of the per-tick promotion function."""

    def test_promotes_past_pending(self, db):
        """A pending row with past scheduled_at is promoted to delivered."""
        past = datetime.now(tz=UTC) - timedelta(minutes=5)
        row = _make_pending(db, scheduled_at=past)

        promoted = promote_due_notifications(db)

        assert promoted == 1
        db.refresh(row)
        assert row.status == "delivered"

    def test_sets_expires_at_at_promotion(self, db):
        """expires_at is computed via calculate_expires_at on transition.

        For habit_nudge with no override, the default window is 4h —
        assert expires_at lands within a reasonable bound of now+4h.
        """
        past = datetime.now(tz=UTC) - timedelta(minutes=5)
        row = _make_pending(db, scheduled_at=past, notification_type="habit_nudge")
        assert row.expires_at is None

        promote_due_notifications(db)

        db.refresh(row)
        assert row.expires_at is not None
        # SQLite strips tz info on roundtrip even with DateTime(timezone=True);
        # normalize to UTC-aware before comparison.
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        delta = expires_at - datetime.now(tz=UTC)
        # Allow a generous bound — the test should not be flaky on slow runs.
        assert timedelta(hours=3, minutes=55) < delta < timedelta(hours=4, minutes=5)

    def test_skips_future_pending(self, db):
        """A pending row with future scheduled_at is NOT promoted."""
        future = datetime.now(tz=UTC) + timedelta(hours=1)
        row = _make_pending(db, scheduled_at=future)

        promoted = promote_due_notifications(db)

        assert promoted == 0
        db.refresh(row)
        assert row.status == "pending"
        assert row.expires_at is None

    def test_skips_already_delivered(self, db):
        """A row already in 'delivered' is not touched by the promoter."""
        past = datetime.now(tz=UTC) - timedelta(minutes=5)
        row = _make_pending(db, scheduled_at=past)
        row.status = "delivered"
        existing_expires = datetime.now(tz=UTC) + timedelta(hours=2)
        row.expires_at = existing_expires
        db.commit()
        db.refresh(row)

        promoted = promote_due_notifications(db)

        assert promoted == 0
        db.refresh(row)
        assert row.status == "delivered"
        # expires_at must not be re-computed on a row the promoter ignored.
        # SQLite strips tz info on roundtrip — compare timestamp values only.
        assert row.expires_at.replace(tzinfo=None) == existing_expires.replace(
            tzinfo=None,
        )

    def test_promotes_only_due_rows_in_mixed_set(self, db):
        """With a mix of past, future, delivered rows, only past+pending promote."""
        past = datetime.now(tz=UTC) - timedelta(minutes=5)
        future = datetime.now(tz=UTC) + timedelta(hours=1)
        due = _make_pending(db, scheduled_at=past)
        not_due = _make_pending(db, scheduled_at=future)
        already = _make_pending(db, scheduled_at=past)
        already.status = "delivered"
        db.commit()

        promoted = promote_due_notifications(db)

        assert promoted == 1
        db.refresh(due)
        db.refresh(not_due)
        db.refresh(already)
        assert due.status == "delivered"
        assert not_due.status == "pending"
        assert already.status == "delivered"


# ---------------------------------------------------------------------------
# _tick — exception handling
# ---------------------------------------------------------------------------


class TestTickExceptionHandling:
    """The poller must survive a tick that raises."""

    def test_tick_swallows_db_exception_and_logs_warning(self, caplog):
        """A session_factory that raises is caught — the poller does not bubble."""

        def boom_factory():
            raise RuntimeError("database is on fire")

        # _tick's finally calls db.close(); since boom_factory raises before
        # returning, there is no db to close — the bare except in _tick
        # catches the factory error too.
        with caplog.at_level(logging.WARNING, logger=delivery_promoter.logger.name):
            _tick(session_factory=boom_factory)

        assert any(
            "tick failed" in rec.message and "database is on fire" in rec.message
            for rec in caplog.records
        )

    def test_tick_continues_after_query_exception(self, caplog, monkeypatch):
        """When the query raises mid-tick, the exception is caught and logged."""

        class ExplodingSession:
            def query(self, *_args, **_kwargs):
                raise RuntimeError("query exploded")

            def close(self) -> None:
                pass

        with caplog.at_level(logging.WARNING, logger=delivery_promoter.logger.name):
            _tick(session_factory=ExplodingSession)

        assert any("query exploded" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Loop lifecycle — the asyncio task starts and cancels cleanly
# ---------------------------------------------------------------------------


class TestPromoterLifecycle:
    """End-to-end: start the loop, observe a tick, cancel cleanly.

    Uses ``asyncio.run`` directly — pytest-asyncio is not in the dev deps and
    adding it for two tests would be a scope expansion not warranted by the
    spec.
    """

    def test_loop_promotes_within_one_interval(self, db, monkeypatch):
        """Insert a due row, run the loop with a tiny interval, observe promotion."""
        monkeypatch.setattr(
            delivery_promoter, "DELIVERY_POLLER_INTERVAL_SECONDS", 0.01,
        )
        past = datetime.now(tz=UTC) - timedelta(minutes=5)
        row = _make_pending(db, scheduled_at=past)
        row_id = row.id

        async def _run():
            task = asyncio.create_task(
                _run_poller(session_factory=TestingSessionLocal),
            )
            try:
                # Give the loop time for at least one full tick + sleep cycle.
                await asyncio.sleep(0.1)
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        asyncio.run(_run())

        # Re-query the row in a fresh session to see the committed state.
        verify_session = TestingSessionLocal()
        try:
            updated = (
                verify_session.query(NotificationQueue)
                .filter(NotificationQueue.id == row_id)
                .one()
            )
            assert updated.status == "delivered"
        finally:
            verify_session.close()

    def test_cancel_terminates_task_without_leak(self, monkeypatch):
        """Cancelling the loop ends the task cleanly with no pending state."""
        monkeypatch.setattr(
            delivery_promoter, "DELIVERY_POLLER_INTERVAL_SECONDS", 0.01,
        )

        async def _run():
            task = asyncio.create_task(
                _run_poller(session_factory=TestingSessionLocal),
            )
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return task

        task = asyncio.run(_run())
        assert task.done()


# ---------------------------------------------------------------------------
# FastAPI integration — startup/shutdown wiring fires without leaking
# ---------------------------------------------------------------------------


class TestFastAPIWiring:
    """install_delivery_promoter wires startup/shutdown without leaking tasks."""

    def test_startup_and_shutdown_run_clean(self, monkeypatch):
        """Entering and exiting a TestClient context starts and stops the loop."""
        monkeypatch.setattr(
            delivery_promoter, "DELIVERY_POLLER_INTERVAL_SECONDS", 0.01,
        )
        # Reset module-level task state so the assertions below are
        # deterministic regardless of test ordering.
        monkeypatch.setattr(delivery_promoter, "_promoter_task", None)

        scratch_app = FastAPI()
        install_delivery_promoter(scratch_app, session_factory=TestingSessionLocal)

        with TestClient(scratch_app):
            # Inside the context the loop is running.
            assert delivery_promoter._promoter_task is not None

        # On exit, the shutdown hook cancels the task and clears the handle.
        assert delivery_promoter._promoter_task is None
