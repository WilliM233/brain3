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

"""Firebase Cloud Messaging (FCM) HTTP v1 client.

Sends push notifications to a single FCM-registered device. Targets the
HTTP v1 endpoint (``https://fcm.googleapis.com/v1/projects/{project_id}/
messages:send``) — the legacy ``fcm.googleapis.com/fcm/send`` API was
deprecated in June 2024 and is not used here.

Authenticates via a Google service-account JSON keyfile loaded from
``settings.FCM_SERVICE_ACCOUNT_JSON_PATH``. Access tokens are cached on
the credentials object and refreshed by ``google-auth`` on demand
(roughly hourly), so callers do not need to manage token lifetime.

The single public function — ``send_notification_to_device`` — returns an
:class:`FcmResult` with a stable ``status`` enum so the caller can react
to ``UNREGISTERED`` / ``INVALID_ARGUMENT`` (token cleanup) without
parsing FCM's error envelopes itself.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

FCM_ENDPOINT_TEMPLATE = (
    "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
)
FCM_OAUTH_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"

# Module-level credentials cache. Populated on first call; reused across
# subsequent calls so the OAuth2 access token lifetime (≈55 min) is
# amortised. Reset by tests via the ``reset_credentials_cache`` helper.
_credentials: Any = None


class FcmStatus(str, Enum):
    """Outcome categories for an FCM send attempt.

    The ``UNREGISTERED`` / ``INVALID_ARGUMENT`` variants are the signal
    callers use to drop a token from ``app_devices``; everything else is
    transient.
    """

    SENT = "sent"
    UNREGISTERED = "unregistered"
    INVALID_ARGUMENT = "invalid_argument"
    AUTH_FAILED = "auth_failed"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    NOT_CONFIGURED = "not_configured"
    NETWORK_ERROR = "network_error"


@dataclass(frozen=True)
class FcmResult:
    """Structured outcome returned from :func:`send_notification_to_device`."""

    status: FcmStatus
    http_status: int | None = None
    error_code: str | None = None
    detail: str | None = None

    @property
    def token_invalidated(self) -> bool:
        """True iff the device token should be removed from ``app_devices``."""
        return self.status in {FcmStatus.UNREGISTERED, FcmStatus.INVALID_ARGUMENT}


def is_configured() -> bool:
    """Return True iff both FCM project id and service-account path are set."""
    return bool(
        settings.FCM_PROJECT_ID and settings.FCM_SERVICE_ACCOUNT_JSON_PATH,
    )


def reset_credentials_cache() -> None:
    """Drop the cached credentials object. Used by tests."""
    global _credentials
    _credentials = None


def _load_credentials() -> Any:
    """Lazily import google-auth and load the service-account credentials.

    Imported lazily so the dependency is only required when FCM is
    actually configured — tests that mock the send path do not need
    google-auth installed for module import to succeed.
    """
    from google.auth.transport.requests import Request as AuthRequest
    from google.oauth2 import service_account

    global _credentials
    if _credentials is None:
        _credentials = service_account.Credentials.from_service_account_file(
            settings.FCM_SERVICE_ACCOUNT_JSON_PATH,
            scopes=[FCM_OAUTH_SCOPE],
        )
    if not _credentials.valid:
        _credentials.refresh(AuthRequest())
    return _credentials


def _classify_error(http_status: int, body: dict[str, Any]) -> FcmResult:
    """Map an FCM error response onto an :class:`FcmResult`.

    FCM HTTP v1 returns errors in the shape::

        {"error": {"code": <int>, "status": "<STRING>", "message": "...",
                   "details": [{"errorCode": "UNREGISTERED", ...}]}}

    The fine-grained ``errorCode`` (in ``details``) is what tells us the
    token is dead; ``status`` alone is too coarse.
    """
    err = body.get("error", {}) if isinstance(body, dict) else {}
    fcm_error_code: str | None = None
    for detail in err.get("details", []) or []:
        if isinstance(detail, dict) and detail.get("errorCode"):
            fcm_error_code = detail["errorCode"]
            break

    detail_msg = err.get("message")

    if fcm_error_code == "UNREGISTERED" or http_status == 404:
        return FcmResult(
            status=FcmStatus.UNREGISTERED,
            http_status=http_status,
            error_code=fcm_error_code,
            detail=detail_msg,
        )
    if fcm_error_code == "INVALID_ARGUMENT" or http_status == 400:
        return FcmResult(
            status=FcmStatus.INVALID_ARGUMENT,
            http_status=http_status,
            error_code=fcm_error_code,
            detail=detail_msg,
        )
    if http_status in (401, 403):
        return FcmResult(
            status=FcmStatus.AUTH_FAILED,
            http_status=http_status,
            error_code=fcm_error_code,
            detail=detail_msg,
        )
    if http_status == 429:
        return FcmResult(
            status=FcmStatus.RATE_LIMITED,
            http_status=http_status,
            error_code=fcm_error_code,
            detail=detail_msg,
        )
    return FcmResult(
        status=FcmStatus.SERVER_ERROR,
        http_status=http_status,
        error_code=fcm_error_code,
        detail=detail_msg,
    )


def send_notification_to_device(
    fcm_token: str, payload: dict[str, Any],
) -> FcmResult:
    """Send a single FCM message to ``fcm_token``.

    ``payload`` is the FCM v1 ``message`` body *without* the ``token``
    field — this function fills that in. Callers build a data-only
    payload (no ``notification`` field) so the companion app's native
    layer can render its own ``NotificationCompat`` with full action
    fidelity (see [2C-06]).

    Returns an :class:`FcmResult` describing the outcome. This function
    does not raise on FCM errors — error categorisation is the caller's
    contract via ``result.status``.
    """
    if not is_configured():
        return FcmResult(
            status=FcmStatus.NOT_CONFIGURED,
            detail=(
                "FCM_PROJECT_ID or FCM_SERVICE_ACCOUNT_JSON_PATH unset; "
                "skipping send"
            ),
        )

    try:
        creds = _load_credentials()
    except Exception as exc:  # noqa: BLE001 — surface credential failures uniformly
        logger.warning("FCM credential load failed: %s", exc)
        return FcmResult(status=FcmStatus.AUTH_FAILED, detail=str(exc))

    body = {"message": {"token": fcm_token, **payload}}
    url = FCM_ENDPOINT_TEMPLATE.format(project_id=settings.FCM_PROJECT_ID)
    encoded = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310 — fixed https FCM endpoint
        url,
        data=encoded,
        method="POST",
        headers={
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            return FcmResult(status=FcmStatus.SENT, http_status=resp.status)
    except urllib.error.HTTPError as exc:
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            error_body = {}
        return _classify_error(exc.code, error_body)
    except urllib.error.URLError as exc:
        logger.warning("FCM network error: %s", exc.reason)
        return FcmResult(status=FcmStatus.NETWORK_ERROR, detail=str(exc.reason))
