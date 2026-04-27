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

"""Bearer token authentication for the App API surface (``/api/app/*``).

Mirrors the pattern in ``brain3-mcp/mcp/auth.py``: a Starlette
``BaseHTTPMiddleware`` that validates ``Authorization: Bearer <token>`` using
``hmac.compare_digest`` for constant-time comparison.

Scoped by path prefix so the existing ``/api/*`` surface (consumed by
``brain3-mcp`` and other internal clients) remains unauthenticated. Only
requests under ``/api/app/`` are gated. The token is sourced from
``settings.APP_BEARER_TOKEN`` (env var ``BRAIN3_APP_BEARER_TOKEN``) and is
intentionally distinct from any MCP token — separate secrets, separate
rotation.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

APP_PATH_PREFIX = "/api/app/"


class AppBearerAuthMiddleware(BaseHTTPMiddleware):
    """Bearer auth on ``/api/app/*``. Pass-through for all other paths.

    Token comparison uses ``hmac.compare_digest`` to prevent timing attacks
    against the shared secret.
    """

    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.url.path.startswith(APP_PATH_PREFIX):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "Missing bearer token"}, status_code=401,
            )

        provided = auth_header[len("Bearer ") :]
        if not hmac.compare_digest(provided, self.token):
            return JSONResponse(
                {"error": "Invalid bearer token"}, status_code=401,
            )

        return await call_next(request)


def install_app_bearer_auth(app: FastAPI, token: str | None) -> None:
    """Mount :class:`AppBearerAuthMiddleware` if ``token`` is set.

    When ``token`` is ``None`` or empty, the middleware is **not** mounted
    and a startup warning is logged. This matches the existing graceful-
    degradation pattern used elsewhere in the app and lets local dev work
    without forcing a token in ``.env``. Production deployments must set
    ``BRAIN3_APP_BEARER_TOKEN`` before exposing the app API.
    """
    if not token:
        logger.warning(
            "BRAIN3_APP_BEARER_TOKEN is not set — /api/app/* endpoints are "
            "UNAUTHENTICATED. Set the env var to enable bearer auth before "
            "exposing the app API.",
        )
        return
    app.add_middleware(AppBearerAuthMiddleware, token=token)
