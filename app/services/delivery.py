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

"""FCM dispatch on the ``pending → delivered`` notification transition.

Single entry-point — :func:`dispatch_push` — invoked from the PATCH
handler (interactive transition) and the delivery promoter (background
transition). Builds a data-only FCM payload so the companion app's
native layer renders the actionable notification itself, and broadcasts
to every row in ``app_devices`` (Phase 2 single-user scale).

Tokens that come back ``UNREGISTERED`` / ``INVALID_ARGUMENT`` are
hard-deleted from ``app_devices`` so a stale device does not keep
generating dispatch attempts.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.models import AppDevice, NotificationQueue
from app.services import fcm

logger = logging.getLogger(__name__)


def build_fcm_payload(notification: NotificationQueue) -> dict:
    """Assemble the data-only FCM v1 payload for ``notification``.

    All values are coerced to strings: FCM v1's ``data`` map is
    ``map<string, string>``, and the companion app's native layer
    expects to receive primitives ready for direct use. ``rule_id`` is
    emitted as an empty string when null so the payload shape is stable.
    """
    canned_responses = notification.canned_responses or []
    return {
        "data": {
            "notification_id": str(notification.id),
            "notification_type": notification.notification_type,
            "message": notification.message,
            "canned_responses": json.dumps(canned_responses),
            "scheduled_date": notification.scheduled_date.isoformat(),
            "rule_id": str(notification.rule_id) if notification.rule_id else "",
        },
        "android": {"priority": "HIGH"},
    }


def dispatch_push(notification: NotificationQueue, db: Session) -> int:
    """Broadcast ``notification`` to every registered device.

    Returns the number of devices the send loop reached SENT on. Tokens
    that come back invalidated are hard-deleted from ``app_devices``
    (per Pass 2 §5: hard-delete chosen for simplicity at Phase 2 scale).

    Failures on one device never block the others — each FCM call's
    result is handled independently. A failure of the whole loop (e.g.
    DB error mid-loop) is allowed to propagate to the caller, which in
    the promoter case is wrapped in the existing tick-level exception
    swallow.
    """
    devices = db.query(AppDevice).all()
    if not devices:
        logger.info(
            "dispatch_push: no registered devices; skipping notification %s",
            notification.id,
        )
        return 0

    payload = build_fcm_payload(notification)
    sent = 0
    invalidated_ids: list = []
    for device in devices:
        try:
            result = fcm.send_notification_to_device(device.fcm_token, payload)
        except Exception as exc:  # noqa: BLE001 — see docstring
            logger.warning(
                "dispatch_push: send to device %s raised %s; continuing",
                device.id,
                exc,
            )
            continue
        if result.status == fcm.FcmStatus.SENT:
            sent += 1
            continue
        if result.token_invalidated:
            invalidated_ids.append(device.id)
            logger.info(
                "dispatch_push: removing invalidated device %s (%s)",
                device.id,
                result.error_code or result.status.value,
            )
            continue
        logger.warning(
            "dispatch_push: send to device %s failed with %s (%s)",
            device.id,
            result.status.value,
            result.detail,
        )

    if invalidated_ids:
        db.query(AppDevice).filter(AppDevice.id.in_(invalidated_ids)).delete(
            synchronize_session=False,
        )
        db.commit()

    return sent
