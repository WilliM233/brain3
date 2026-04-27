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

"""Tests for the App Device registration endpoints ([2C-05])."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import AppBearerAuthMiddleware
from app.database import get_db
from app.models import AppDevice
from app.routers.devices import router as devices_router
from tests.conftest import TestingSessionLocal

DEVICES_PATH = "/api/app/devices"
TOKEN_A = "fcm-token-aaaaaaaaaaaaaaa"
TOKEN_B = "fcm-token-bbbbbbbbbbbbbbb"


# ---------------------------------------------------------------------------
# POST — register / upsert
# ---------------------------------------------------------------------------


class TestRegisterDevice:
    """``POST /api/app/devices`` insert + upsert semantics."""

    def test_first_registration_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            DEVICES_PATH,
            json={"fcm_token": TOKEN_A, "platform": "android", "label": "Pixel 8"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["fcm_token"] == TOKEN_A
        assert body["platform"] == "android"
        assert body["label"] == "Pixel 8"
        assert "id" in body
        assert "registered_at" in body
        assert "last_seen_at" in body

    def test_duplicate_token_returns_200_with_updated_last_seen(
        self, client: TestClient,
    ) -> None:
        first = client.post(
            DEVICES_PATH, json={"fcm_token": TOKEN_A, "platform": "android"},
        )
        assert first.status_code == 201
        first_seen = first.json()["last_seen_at"]
        first_id = first.json()["id"]

        second = client.post(
            DEVICES_PATH,
            json={"fcm_token": TOKEN_A, "platform": "android", "label": "renamed"},
        )
        assert second.status_code == 200
        body = second.json()
        assert body["id"] == first_id
        assert body["label"] == "renamed"
        assert body["last_seen_at"] >= first_seen

    def test_invalid_platform_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            DEVICES_PATH,
            json={"fcm_token": TOKEN_A, "platform": "windows-phone"},
        )
        assert resp.status_code == 422

    def test_missing_fcm_token_returns_422(self, client: TestClient) -> None:
        resp = client.post(DEVICES_PATH, json={"platform": "android"})
        assert resp.status_code == 422

    def test_empty_fcm_token_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            DEVICES_PATH, json={"fcm_token": "", "platform": "android"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET list
# ---------------------------------------------------------------------------


class TestListDevices:
    """``GET /api/app/devices`` returns the envelope shape."""

    def test_empty_list(self, client: TestClient) -> None:
        resp = client.get(DEVICES_PATH)
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "count": 0}

    def test_lists_registered_devices(self, client: TestClient) -> None:
        client.post(
            DEVICES_PATH, json={"fcm_token": TOKEN_A, "platform": "android"},
        )
        client.post(
            DEVICES_PATH, json={"fcm_token": TOKEN_B, "platform": "ios"},
        )
        resp = client.get(DEVICES_PATH)
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        tokens = {item["fcm_token"] for item in body["items"]}
        assert tokens == {TOKEN_A, TOKEN_B}


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


class TestUnregisterDevice:
    """``DELETE /api/app/devices/{id}`` removes the row."""

    def test_delete_removes_device(self, client: TestClient, db) -> None:
        created = client.post(
            DEVICES_PATH, json={"fcm_token": TOKEN_A, "platform": "android"},
        ).json()

        resp = client.delete(f"{DEVICES_PATH}/{created['id']}")
        assert resp.status_code == 204

        remaining = db.query(AppDevice).count()
        assert remaining == 0

    def test_delete_nonexistent_returns_404(self, client: TestClient) -> None:
        bogus = uuid.uuid4()
        resp = client.delete(f"{DEVICES_PATH}/{bogus}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Bearer-auth integration — devices router gated by /api/app/* middleware
# ---------------------------------------------------------------------------


class TestDevicesBearerAuth:
    """The devices router sits behind ``AppBearerAuthMiddleware``.

    ``app/main.py`` mounts the middleware only when ``APP_BEARER_TOKEN``
    is set, so the default test client (token unset) does not exercise
    the gate. Build a fresh app with the middleware enabled to prove
    that routing is correct: ``POST /api/app/devices`` without the
    bearer is 401, with the bearer is normal CRUD.
    """

    TOKEN = "test-bearer-fffffffffffffffff"  # noqa: S105 — fixture only

    def _build_app(self, db) -> TestClient:
        app = FastAPI()
        app.add_middleware(AppBearerAuthMiddleware, token=self.TOKEN)
        app.include_router(devices_router, prefix="/api/app/devices")

        def _override():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _override
        return TestClient(app)

    def test_post_without_bearer_returns_401(self, db) -> None:
        client = self._build_app(db)
        resp = client.post(
            DEVICES_PATH,
            json={"fcm_token": TOKEN_A, "platform": "android"},
        )
        assert resp.status_code == 401

    def test_post_with_bearer_returns_201(self, db) -> None:
        client = self._build_app(db)
        resp = client.post(
            DEVICES_PATH,
            json={"fcm_token": TOKEN_A, "platform": "android"},
            headers={"Authorization": f"Bearer {self.TOKEN}"},
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Direct ORM model tests — insert / upsert / delete contract
# ---------------------------------------------------------------------------


class TestAppDeviceModel:
    """Direct ORM-level checks of the ``app_devices`` mapping."""

    def test_insert_and_unique_token(self, db) -> None:
        device = AppDevice(fcm_token=TOKEN_A, platform="android", label="Pixel")
        db.add(device)
        db.commit()
        db.refresh(device)
        assert device.id is not None
        assert device.registered_at is not None
        assert device.last_seen_at is not None

    def test_duplicate_fcm_token_violates_unique(self, db) -> None:
        from sqlalchemy.exc import IntegrityError

        db.add(AppDevice(fcm_token=TOKEN_A, platform="android"))
        db.commit()

        db.add(AppDevice(fcm_token=TOKEN_A, platform="ios"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_delete_drops_row(self, db) -> None:
        device = AppDevice(fcm_token=TOKEN_A, platform="android")
        db.add(device)
        db.commit()

        db.delete(device)
        db.commit()

        # Use a fresh session to confirm the delete is committed.
        verify = TestingSessionLocal()
        try:
            assert verify.query(AppDevice).count() == 0
        finally:
            verify.close()
