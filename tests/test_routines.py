"""Tests for Routine CRUD, schedule management, and completion endpoints."""

from datetime import date, timedelta

from tests.conftest import FAKE_UUID, make_domain, make_routine

# ---------------------------------------------------------------------------
# POST /api/routines
# ---------------------------------------------------------------------------

class TestCreateRoutine:

    def test_create_routine(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/routines",
            json={"domain_id": domain["id"], "title": "Morning walk", "frequency": "daily"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Morning walk"
        assert body["frequency"] == "daily"
        assert body["status"] == "active"
        assert body["current_streak"] == 0
        assert body["best_streak"] == 0
        assert body["last_completed"] is None

    def test_create_routine_with_optional_fields(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/routines",
            json={
                "domain_id": domain["id"],
                "title": "Meditate",
                "frequency": "weekdays",
                "description": "10 min mindfulness",
                "energy_cost": 2,
                "activation_friction": 3,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["description"] == "10 min mindfulness"
        assert body["energy_cost"] == 2
        assert body["activation_friction"] == 3

    def test_create_routine_missing_title(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/routines",
            json={"domain_id": domain["id"], "frequency": "daily"},
        )
        assert resp.status_code == 422

    def test_create_routine_invalid_domain(self, client):
        resp = client.post(
            "/api/routines",
            json={"domain_id": FAKE_UUID, "title": "Orphan", "frequency": "daily"},
        )
        assert resp.status_code == 400

    def test_create_routine_energy_out_of_range(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/routines",
            json={
                "domain_id": domain["id"], "title": "Bad", "frequency": "daily",
                "energy_cost": 6,
            },
        )
        assert resp.status_code == 422

    def test_create_routine_friction_zero(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/routines",
            json={
                "domain_id": domain["id"], "title": "Bad", "frequency": "daily",
                "activation_friction": 0,
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/routines
# ---------------------------------------------------------------------------

class TestListRoutines:

    def test_list_routines_empty(self, client):
        resp = client.get("/api/routines")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_routines(self, client):
        domain = make_domain(client)
        make_routine(client, domain["id"], title="A")
        make_routine(client, domain["id"], title="B")
        resp = client.get("/api/routines")
        assert len(resp.json()) == 2

    def test_filter_by_domain_id(self, client):
        d1 = make_domain(client, name="D1")
        d2 = make_domain(client, name="D2")
        make_routine(client, d1["id"], title="R1")
        make_routine(client, d2["id"], title="R2")
        resp = client.get(f"/api/routines?domain_id={d1['id']}")
        routines = resp.json()
        assert len(routines) == 1
        assert routines[0]["title"] == "R1"

    def test_filter_by_status(self, client):
        domain = make_domain(client)
        make_routine(client, domain["id"], title="Active", status="active")
        make_routine(client, domain["id"], title="Paused", status="paused")
        resp = client.get("/api/routines?status=paused")
        routines = resp.json()
        assert len(routines) == 1
        assert routines[0]["title"] == "Paused"

    def test_filter_by_frequency(self, client):
        domain = make_domain(client)
        make_routine(client, domain["id"], title="Daily", frequency="daily")
        make_routine(client, domain["id"], title="Weekly", frequency="weekly")
        resp = client.get("/api/routines?frequency=weekly")
        routines = resp.json()
        assert len(routines) == 1
        assert routines[0]["title"] == "Weekly"

    def test_filter_streak_broken(self, client):
        domain = make_domain(client)
        make_routine(client, domain["id"], title="Broken")
        r_ok = make_routine(client, domain["id"], title="OK")
        make_routine(client, domain["id"], title="Paused", status="paused")

        # Give "OK" a streak by completing it
        client.post(f"/api/routines/{r_ok['id']}/complete")

        resp = client.get("/api/routines?streak_broken=true")
        routines = resp.json()
        assert len(routines) == 1
        assert routines[0]["title"] == "Broken"
        # Paused routine should NOT appear even though streak is 0


# ---------------------------------------------------------------------------
# GET /api/routines/{id}
# ---------------------------------------------------------------------------

class TestGetRoutine:

    def test_get_routine_detail(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.get(f"/api/routines/{routine['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == routine["title"]
        assert "schedules" in body
        assert body["schedules"] == []

    def test_get_routine_with_schedules(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        client.post(
            f"/api/routines/{routine['id']}/schedules",
            json={"day_of_week": "monday", "time_of_day": "morning"},
        )
        resp = client.get(f"/api/routines/{routine['id']}")
        assert len(resp.json()["schedules"]) == 1

    def test_get_routine_not_found(self, client):
        resp = client.get(f"/api/routines/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/routines/{id}
# ---------------------------------------------------------------------------

class TestUpdateRoutine:

    def test_patch_routine(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"], title="Old")
        resp = client.patch(
            f"/api/routines/{routine['id']}", json={"title": "New"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    def test_patch_routine_partial(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"], title="Keep", energy_cost=3)
        resp = client.patch(
            f"/api/routines/{routine['id']}", json={"energy_cost": 1},
        )
        body = resp.json()
        assert body["title"] == "Keep"
        assert body["energy_cost"] == 1

    def test_patch_routine_not_found(self, client):
        resp = client.patch(f"/api/routines/{FAKE_UUID}", json={"title": "X"})
        assert resp.status_code == 404

    def test_patch_routine_invalid_energy(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.patch(
            f"/api/routines/{routine['id']}", json={"energy_cost": 7},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/routines/{id}
# ---------------------------------------------------------------------------

class TestDeleteRoutine:

    def test_delete_routine(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.delete(f"/api/routines/{routine['id']}")
        assert resp.status_code == 204
        resp = client.get(f"/api/routines/{routine['id']}")
        assert resp.status_code == 404

    def test_delete_routine_cascades_schedules(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        client.post(
            f"/api/routines/{routine['id']}/schedules",
            json={"day_of_week": "monday", "time_of_day": "morning"},
        )
        client.delete(f"/api/routines/{routine['id']}")
        resp = client.get(f"/api/routines/{routine['id']}/schedules")
        assert resp.status_code == 404

    def test_delete_routine_not_found(self, client):
        resp = client.delete(f"/api/routines/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/routines/{id}/complete
# ---------------------------------------------------------------------------

class TestCompleteRoutine:

    def test_first_completion(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        assert resp.status_code == 200
        body = resp.json()
        assert body["current_streak"] == 1
        assert body["best_streak"] == 1
        assert body["streak_was_broken"] is False
        assert body["completed_date"] == date.today().isoformat()

    def test_streak_continues(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"completed_date": yesterday},
        )
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        assert body["current_streak"] == 2
        assert body["streak_was_broken"] is False

    def test_streak_breaks(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        three_days_ago = (date.today() - timedelta(days=3)).isoformat()
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"completed_date": three_days_ago},
        )
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        assert body["current_streak"] == 1
        assert body["streak_was_broken"] is True

    def test_best_streak_updates(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        # Build a streak of 3
        for i in range(3, 0, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            client.post(
                f"/api/routines/{routine['id']}/complete",
                json={"completed_date": d},
            )
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        assert resp.json()["best_streak"] == 4

    def test_same_day_idempotent(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        client.post(f"/api/routines/{routine['id']}/complete")
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        assert body["current_streak"] == 1
        assert body["streak_was_broken"] is False

    def test_complete_non_active_rejected(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"], status="paused")
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        assert resp.status_code == 409

    def test_complete_not_found(self, client):
        resp = client.post(f"/api/routines/{FAKE_UUID}/complete")
        assert resp.status_code == 404

    def test_backdate_completion(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        resp = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"completed_date": yesterday},
        )
        assert resp.status_code == 200
        assert resp.json()["completed_date"] == yesterday


# ---------------------------------------------------------------------------
# Schedule management — /api/routines/{routine_id}/schedules
# ---------------------------------------------------------------------------

class TestScheduleManagement:

    def test_add_schedule(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.post(
            f"/api/routines/{routine['id']}/schedules",
            json={"day_of_week": "monday", "time_of_day": "morning"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["day_of_week"] == "monday"
        assert body["time_of_day"] == "morning"
        assert body["routine_id"] == routine["id"]

    def test_add_schedule_with_window(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.post(
            f"/api/routines/{routine['id']}/schedules",
            json={
                "day_of_week": "friday",
                "time_of_day": "08:00",
                "preferred_window": "06:00-10:00",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["preferred_window"] == "06:00-10:00"

    def test_list_schedules(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        client.post(
            f"/api/routines/{routine['id']}/schedules",
            json={"day_of_week": "monday", "time_of_day": "morning"},
        )
        client.post(
            f"/api/routines/{routine['id']}/schedules",
            json={"day_of_week": "wednesday", "time_of_day": "evening"},
        )
        resp = client.get(f"/api/routines/{routine['id']}/schedules")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_delete_schedule(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        sched = client.post(
            f"/api/routines/{routine['id']}/schedules",
            json={"day_of_week": "monday", "time_of_day": "morning"},
        ).json()
        resp = client.delete(
            f"/api/routines/{routine['id']}/schedules/{sched['id']}"
        )
        assert resp.status_code == 204
        resp = client.get(f"/api/routines/{routine['id']}/schedules")
        assert len(resp.json()) == 0

    def test_add_schedule_invalid_routine(self, client):
        resp = client.post(
            f"/api/routines/{FAKE_UUID}/schedules",
            json={"day_of_week": "monday", "time_of_day": "morning"},
        )
        assert resp.status_code == 404

    def test_list_schedules_invalid_routine(self, client):
        resp = client.get(f"/api/routines/{FAKE_UUID}/schedules")
        assert resp.status_code == 404

    def test_delete_schedule_not_found(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.delete(
            f"/api/routines/{routine['id']}/schedules/{FAKE_UUID}"
        )
        assert resp.status_code == 404
