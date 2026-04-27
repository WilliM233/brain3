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

"""Default canned responses, expiry windows, and retention for the notification queue."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.config import settings

CANNED_RESPONSE_DEFAULTS: dict[str, list[str]] = {
    "habit_nudge": [
        "Already done",
        "Doing it now",
        "I forgot, on it",
        "Skip today",
    ],
    "routine_checklist": [
        "All done",
        "Partial",
        "Skipping tonight",
    ],
    "checkin_prompt": [
        "1",
        "2",
        "3",
        "4",
        "5",
    ],
    "time_block_reminder": [
        "On it",
        "Need 10 more minutes",
        "Skipping",
    ],
    "deadline_event_alert": [
        "Acknowledged",
        "Reschedule",
    ],
    "pattern_observation": [
        "Thanks, I'll look at it",
        "Noted",
        "Let's talk about it",
    ],
    "stale_work_nudge": [
        "I'll look",
        "Not today",
        "Remove from my list",
    ],
}


def get_default_responses(notification_type: str) -> list[str] | None:
    """Return the default canned responses for a notification type, or None."""
    defaults = CANNED_RESPONSE_DEFAULTS.get(notification_type)
    if defaults is not None:
        return list(defaults)
    return None


def validate_canned_responses(responses: list[str]) -> None:
    """Validate a canned_responses list. Raises ValueError on failure."""
    if not isinstance(responses, list):
        msg = "canned_responses must be an array of strings"
        raise ValueError(msg)

    if len(responses) < 1:
        msg = "canned_responses must have at least 1 option"
        raise ValueError(msg)

    if len(responses) > 10:
        msg = "canned_responses cannot exceed 10 options"
        raise ValueError(msg)

    seen: set[str] = set()
    for item in responses:
        if not isinstance(item, str):
            msg = "canned_responses must be an array of strings"
            raise ValueError(msg)

        if not item.strip():
            msg = "Canned response options cannot be blank"
            raise ValueError(msg)

        if len(item) < 1 or len(item) > 200:
            msg = "Each canned response must be 1-200 characters"
            raise ValueError(msg)

        if item in seen:
            msg = "canned_responses contains duplicate entries"
            raise ValueError(msg)
        seen.add(item)


# ---------------------------------------------------------------------------
# Expiry window defaults (per notification type)
# ---------------------------------------------------------------------------

EXPIRY_DEFAULTS: dict[str, timedelta] = {
    "habit_nudge": timedelta(hours=4),
    # routine_checklist resolves to EOD-local at calc time; the timedelta
    # here is a fallback used only when scheduled_date is missing.
    "routine_checklist": timedelta(hours=4),
    "checkin_prompt": timedelta(hours=2),
    # time_block_reminder is floored by block_duration when supplied; default
    # 30m applies when block_duration is unknown at delivery time.
    "time_block_reminder": timedelta(minutes=30),
    "deadline_event_alert": timedelta(hours=0),  # special: expires at target deadline
    "pattern_observation": timedelta(hours=48),
    "stale_work_nudge": timedelta(hours=24),
}

# ---------------------------------------------------------------------------
# Retention policy
# ---------------------------------------------------------------------------

RETENTION_DAYS: int = 90


# ---------------------------------------------------------------------------
# Expiry calculation
# ---------------------------------------------------------------------------


def calculate_expires_at(
    notification_type: str,
    delivered_at: datetime,
    existing_expires_at: datetime | None = None,
    *,
    scheduled_date: date | None = None,
    block_duration: timedelta | None = None,
) -> datetime | None:
    """Calculate the expiry timestamp for a notification at delivery time.

    If *existing_expires_at* is already set (per-notification override), it is
    returned unchanged.  Otherwise the type default is applied:

    - ``deadline_event_alert`` with no override falls back to 24h from delivery
      (the creator *should* have set an explicit ``expires_at``).
    - ``time_block_reminder``: ``delivered_at + min(30m, block_duration)`` when
      *block_duration* is supplied; otherwise the 30m default.
    - ``routine_checklist``: midnight at the start of the day after
      *scheduled_date*, in ``settings.SERVER_TZ`` (EOD-local). Falls back to
      the 4h default if *scheduled_date* is not supplied.
    - All other types: ``delivered_at + EXPIRY_DEFAULTS[type]``.
    """
    if existing_expires_at is not None:
        return existing_expires_at

    if notification_type == "deadline_event_alert":
        return delivered_at + timedelta(hours=24)

    if notification_type == "time_block_reminder":
        floor = EXPIRY_DEFAULTS["time_block_reminder"]
        if block_duration is not None:
            floor = min(floor, block_duration)
        return delivered_at + floor

    if notification_type == "routine_checklist" and scheduled_date is not None:
        next_day = scheduled_date + timedelta(days=1)
        return datetime.combine(next_day, time(0, 0), tzinfo=settings.server_tz)

    default_delta = EXPIRY_DEFAULTS.get(notification_type)
    if default_delta is None:
        return None

    return delivered_at + default_delta


# ---------------------------------------------------------------------------
# Query helpers (called by scheduler — Stream C)
# ---------------------------------------------------------------------------


def get_expired_notifications(session: Session) -> list:
    """Return delivered notifications whose expiry window has passed."""
    from app.models import NotificationQueue

    now = datetime.now(tz=UTC)
    return (
        session.query(NotificationQueue)
        .filter(
            NotificationQueue.status == "delivered",
            NotificationQueue.expires_at.isnot(None),
            NotificationQueue.expires_at < now,
        )
        .all()
    )


def get_retention_candidates(
    session: Session, retention_days: int = RETENTION_DAYS,
) -> list:
    """Return terminal-state notifications older than *retention_days*.

    Uses ``updated_at`` as the reference timestamp.  Terminal states are
    ``responded`` and ``expired``.
    """
    from app.models import NotificationQueue

    cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)
    return (
        session.query(NotificationQueue)
        .filter(
            NotificationQueue.status.in_(["responded", "expired"]),
            NotificationQueue.updated_at < cutoff,
        )
        .all()
    )
