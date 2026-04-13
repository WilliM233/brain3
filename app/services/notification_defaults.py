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

"""Default canned responses and validation for the notification queue."""

from __future__ import annotations

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
