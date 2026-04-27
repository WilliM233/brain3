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

"""Lightweight delivery promoter background task ([2C-05a]).

Polls ``notification_queue`` every ``DELIVERY_POLLER_INTERVAL_SECONDS`` for
rows in ``status='pending'`` whose ``scheduled_at`` is in the past, and
transitions each such row to ``status='delivered'``. ``expires_at`` is
recomputed at the transition via ``calculate_expires_at``, mirroring the
side-effect on the PATCH ``status='delivered'`` path.

This is the proto-Stream-D scaffolding shipped under [2C-05a]: the smallest
asyncio task that satisfies the v2.0.0 notification loop. Stream D, when it
runs, expands this module into full scheduler infrastructure (advance batch
scheduling, time-block triggers, drift-tolerant execution).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Callable

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import NotificationQueue
from app.services.notification_defaults import calculate_expires_at

logger = logging.getLogger(__name__)

# 30s is the Pass 2 recommended default — worst-case 30s delivery latency at
# Phase 2 single-user scale. Module-level so tests can monkey-patch it.
DELIVERY_POLLER_INTERVAL_SECONDS: float = 30.0

SessionFactory = Callable[[], Session]

_promoter_task: asyncio.Task[None] | None = None


def promote_due_notifications(db: Session) -> int:
    """Promote all pending notifications whose ``scheduled_at`` is in the past.

    Transitions each eligible row to ``delivered`` and recomputes
    ``expires_at`` via ``calculate_expires_at``. The expires_at logic
    matches the PATCH handler's ``status='delivered'`` side-effect — kept
    inline rather than extracted into a shared helper because [2C-05] FCM
    dispatch is the natural moment to refactor this seam (see PR body).

    Returns the number of rows promoted.
    """
    now = datetime.now(tz=UTC)
    due = (
        db.query(NotificationQueue)
        .filter(
            NotificationQueue.status == "pending",
            NotificationQueue.scheduled_at <= now,
        )
        .all()
    )
    for row in due:
        row.status = "delivered"
        row.expires_at = calculate_expires_at(
            row.notification_type,
            now,
            row.expires_at,
            scheduled_date=row.scheduled_date,
        )
    if due:
        db.commit()
    return len(due)


def _tick(session_factory: SessionFactory = SessionLocal) -> None:
    """One promoter tick. Catches and logs any exception so the loop survives.

    The exception swallow is deliberate — one bad row (or a transient DB
    blip) must not kill the poller. Hardening (retry, backoff, dead-letter)
    is a Stream D concern, explicitly out of scope here.
    """
    db: Session | None = None
    try:
        db = session_factory()
        count = promote_due_notifications(db)
        logger.info("delivery promoter: promoted %d notification(s)", count)
    except Exception as exc:  # noqa: BLE001 — see docstring
        logger.warning("delivery promoter: tick failed: %s", exc)
    finally:
        if db is not None:
            db.close()


async def _run_poller(session_factory: SessionFactory = SessionLocal) -> None:
    """Run the promoter loop until cancelled.

    Cancellation propagates from ``asyncio.sleep``; ``_tick`` is a quick
    sync call between sleeps, so a clean cancel-on-shutdown is reliable.
    """
    while True:
        _tick(session_factory)
        await asyncio.sleep(DELIVERY_POLLER_INTERVAL_SECONDS)


def install_delivery_promoter(
    app: FastAPI, session_factory: SessionFactory = SessionLocal,
) -> None:
    """Register startup/shutdown hooks that run the delivery promoter.

    ``session_factory`` is injectable for tests; production wiring uses the
    default ``SessionLocal``.
    """

    @app.on_event("startup")
    async def _start_promoter() -> None:
        global _promoter_task
        _promoter_task = asyncio.create_task(_run_poller(session_factory))
        logger.info(
            "delivery promoter started (interval=%ss)",
            DELIVERY_POLLER_INTERVAL_SECONDS,
        )

    @app.on_event("shutdown")
    async def _stop_promoter() -> None:
        global _promoter_task
        if _promoter_task is None:
            return
        _promoter_task.cancel()
        try:
            await _promoter_task
        except asyncio.CancelledError:
            pass
        _promoter_task = None
        logger.info("delivery promoter stopped")
