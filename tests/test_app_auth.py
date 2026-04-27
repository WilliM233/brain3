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

"""Tests for the App API bearer-token middleware (``app/auth.py``).

Covers the four acceptance paths from issue #200 — missing header, wrong
token, correct token, env-unset warning — plus the no-regression check that
non-``/api/app/*`` routes stay unauthenticated when the middleware is on.

Each test builds its own ``FastAPI`` app rather than reusing the global
``app.main.app``: that app's middleware is wired up at import time from the
real env, so per-test scenarios (no-token, known-token) need a clean
instance.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import AppBearerAuthMiddleware, install_app_bearer_auth

TEST_TOKEN = "test-bearer-token-abc123"  # noqa: S105 — fixture, not a real secret


def _app_with_token(token: str) -> FastAPI:
    """Build a fresh app with the middleware mounted to ``token``."""
    fresh = FastAPI()
    fresh.add_middleware(AppBearerAuthMiddleware, token=token)

    @fresh.get("/api/app/health")
    def app_health() -> dict:
        return {"ok": True}

    @fresh.get("/api/notifications/ping")
    def notif_ping() -> dict:
        return {"pong": True}

    return fresh


@pytest.fixture
def authed_client() -> TestClient:
    """TestClient against a fresh app with the bearer middleware enabled."""
    return TestClient(_app_with_token(TEST_TOKEN))


# ---------------------------------------------------------------------------
# Acceptance paths — issue #200
# ---------------------------------------------------------------------------

def test_missing_authorization_header_returns_401(authed_client: TestClient) -> None:
    """No Authorization header → 401 with the missing-token error body."""
    resp = authed_client.get("/api/app/health")
    assert resp.status_code == 401
    assert resp.json() == {"error": "Missing bearer token"}


def test_wrong_token_returns_401(authed_client: TestClient) -> None:
    """Authorization header with the wrong secret → 401 invalid-token."""
    resp = authed_client.get(
        "/api/app/health",
        headers={"Authorization": "Bearer not-the-real-token"},
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "Invalid bearer token"}


def test_correct_token_returns_200(authed_client: TestClient) -> None:
    """Authorization header with the right secret → endpoint runs."""
    resp = authed_client.get(
        "/api/app/health",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_unset_token_emits_warning_and_skips_middleware(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``install_app_bearer_auth`` warns and stays a no-op when token is unset."""
    fresh = FastAPI()

    @fresh.get("/api/app/health")
    def app_health() -> dict:
        return {"ok": True}

    with caplog.at_level(logging.WARNING, logger="app.auth"):
        install_app_bearer_auth(fresh, None)

    assert any(
        "BRAIN3_APP_BEARER_TOKEN is not set" in record.message
        and record.levelno == logging.WARNING
        for record in caplog.records
    ), f"Expected unset-token warning; got: {[r.message for r in caplog.records]}"

    # Middleware was not mounted: the endpoint serves without an auth header.
    with TestClient(fresh) as client:
        resp = client.get("/api/app/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# ---------------------------------------------------------------------------
# Regression — issue #200: existing /api/* routes stay unauthenticated
# ---------------------------------------------------------------------------

def test_non_app_paths_pass_through_when_middleware_active(
    authed_client: TestClient,
) -> None:
    """Routes outside ``/api/app/*`` are not gated even with the middleware on.

    Guards the no-regression criterion: ``/api/notifications/*`` (and every
    other existing route consumed by MCP / internal clients) must still
    answer without an Authorization header.
    """
    resp = authed_client.get("/api/notifications/ping")
    assert resp.status_code == 200
    assert resp.json() == {"pong": True}


def test_empty_bearer_value_returns_401(authed_client: TestClient) -> None:
    """Header present but value empty → still missing-token (no Bearer prefix)."""
    resp = authed_client.get(
        "/api/app/health",
        headers={"Authorization": ""},
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "Missing bearer token"}
