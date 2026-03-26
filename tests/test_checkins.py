"""Tests for State Check-in CRUD endpoints."""

from tests.conftest import FAKE_UUID, make_checkin

# ---------------------------------------------------------------------------
# POST /api/checkins
# ---------------------------------------------------------------------------

class TestCreateCheckin:

    def test_create_checkin(self, client):
        resp = client.post(
            "/api/checkins",
            json={"checkin_type": "morning", "energy_level": 3, "mood": 4, "focus_level": 2},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["checkin_type"] == "morning"
        assert body["energy_level"] == 3
        assert body["mood"] == 4
        assert body["focus_level"] == 2
        assert body["logged_at"] is not None

    def test_create_freeform_only(self, client):
        resp = client.post(
            "/api/checkins",
            json={"checkin_type": "freeform", "freeform_note": "Feeling scattered today"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["freeform_note"] == "Feeling scattered today"
        assert body["energy_level"] is None
        assert body["mood"] is None

    def test_create_scales_only(self, client):
        resp = client.post(
            "/api/checkins",
            json={"checkin_type": "micro", "energy_level": 5},
        )
        assert resp.status_code == 201
        assert resp.json()["freeform_note"] is None

    def test_create_with_context(self, client):
        resp = client.post(
            "/api/checkins",
            json={"checkin_type": "evening", "context": "work_day", "mood": 3},
        )
        assert resp.status_code == 201
        assert resp.json()["context"] == "work_day"

    def test_create_missing_type(self, client):
        resp = client.post("/api/checkins", json={"energy_level": 3})
        assert resp.status_code == 422

    def test_create_invalid_energy(self, client):
        resp = client.post(
            "/api/checkins", json={"checkin_type": "morning", "energy_level": 6},
        )
        assert resp.status_code == 422

    def test_create_invalid_mood(self, client):
        resp = client.post(
            "/api/checkins", json={"checkin_type": "morning", "mood": 0},
        )
        assert resp.status_code == 422

    def test_create_invalid_focus(self, client):
        resp = client.post(
            "/api/checkins", json={"checkin_type": "morning", "focus_level": -1},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/checkins
# ---------------------------------------------------------------------------

class TestListCheckins:

    def test_list_checkins_empty(self, client):
        resp = client.get("/api/checkins")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_checkins(self, client):
        make_checkin(client, checkin_type="morning")
        make_checkin(client, checkin_type="evening")
        resp = client.get("/api/checkins")
        assert len(resp.json()) == 2

    def test_filter_by_type(self, client):
        make_checkin(client, checkin_type="morning")
        make_checkin(client, checkin_type="evening")
        resp = client.get("/api/checkins?checkin_type=morning")
        checkins = resp.json()
        assert len(checkins) == 1
        assert checkins[0]["checkin_type"] == "morning"

    def test_filter_by_context(self, client):
        make_checkin(client, checkin_type="morning", context="work_day")
        make_checkin(client, checkin_type="morning", context="day_off")
        resp = client.get("/api/checkins?context=work_day")
        checkins = resp.json()
        assert len(checkins) == 1
        assert checkins[0]["context"] == "work_day"

    def test_filter_logged_after(self, client):
        make_checkin(client, checkin_type="morning")
        resp = client.get("/api/checkins?logged_after=2020-01-01T00:00:00")
        assert len(resp.json()) == 1

    def test_filter_logged_before(self, client):
        make_checkin(client, checkin_type="morning")
        resp = client.get("/api/checkins?logged_before=2099-12-31T23:59:59")
        assert len(resp.json()) == 1

    def test_filter_composable_date_range(self, client):
        make_checkin(client, checkin_type="morning")
        resp = client.get(
            "/api/checkins?logged_after=2020-01-01T00:00:00&logged_before=2099-12-31T23:59:59"
        )
        assert len(resp.json()) == 1

    def test_reverse_chronological_order(self, client, db):
        """Verify results are ordered by logged_at descending."""
        from datetime import datetime, timezone

        from app.models import StateCheckin

        early = StateCheckin(
            checkin_type="morning",
            logged_at=datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc),
        )
        late = StateCheckin(
            checkin_type="evening",
            logged_at=datetime(2026, 3, 1, 20, 0, tzinfo=timezone.utc),
        )
        db.add_all([early, late])
        db.commit()

        resp = client.get("/api/checkins")
        checkins = resp.json()
        assert checkins[0]["checkin_type"] == "evening"
        assert checkins[1]["checkin_type"] == "morning"


# ---------------------------------------------------------------------------
# GET /api/checkins/{id}
# ---------------------------------------------------------------------------

class TestGetCheckin:

    def test_get_checkin(self, client):
        checkin = make_checkin(client, checkin_type="midday", mood=3)
        resp = client.get(f"/api/checkins/{checkin['id']}")
        assert resp.status_code == 200
        assert resp.json()["checkin_type"] == "midday"

    def test_get_checkin_not_found(self, client):
        resp = client.get(f"/api/checkins/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/checkins/{id}
# ---------------------------------------------------------------------------

class TestUpdateCheckin:

    def test_patch_checkin(self, client):
        checkin = make_checkin(client, checkin_type="morning", mood=2)
        resp = client.patch(
            f"/api/checkins/{checkin['id']}", json={"mood": 4},
        )
        assert resp.status_code == 200
        assert resp.json()["mood"] == 4

    def test_patch_checkin_partial(self, client):
        checkin = make_checkin(
            client, checkin_type="morning", energy_level=3, mood=2,
        )
        resp = client.patch(
            f"/api/checkins/{checkin['id']}", json={"energy_level": 5},
        )
        body = resp.json()
        assert body["energy_level"] == 5
        assert body["mood"] == 2  # unchanged

    def test_patch_checkin_not_found(self, client):
        resp = client.patch(
            f"/api/checkins/{FAKE_UUID}", json={"mood": 3},
        )
        assert resp.status_code == 404

    def test_patch_checkin_invalid_scale(self, client):
        checkin = make_checkin(client)
        resp = client.patch(
            f"/api/checkins/{checkin['id']}", json={"focus_level": 10},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/checkins/{id}
# ---------------------------------------------------------------------------

class TestDeleteCheckin:

    def test_delete_checkin(self, client):
        checkin = make_checkin(client)
        resp = client.delete(f"/api/checkins/{checkin['id']}")
        assert resp.status_code == 204
        resp = client.get(f"/api/checkins/{checkin['id']}")
        assert resp.status_code == 404

    def test_delete_checkin_not_found(self, client):
        resp = client.delete(f"/api/checkins/{FAKE_UUID}")
        assert resp.status_code == 404
