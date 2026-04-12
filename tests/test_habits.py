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

"""Tests for Habit CRUD endpoints."""

from tests.conftest import FAKE_UUID, make_domain, make_habit, make_routine

# ---------------------------------------------------------------------------
# POST /api/habits
# ---------------------------------------------------------------------------


class TestCreateHabit:

    def test_create_standalone_habit(self, client):
        resp = client.post(
            "/api/habits",
            json={"title": "Drink water", "frequency": "daily"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Drink water"
        assert body["frequency"] == "daily"
        assert body["status"] == "active"
        assert body["routine_id"] is None
        assert body["notification_frequency"] == "none"
        assert body["scaffolding_status"] == "tracking"
        assert body["current_streak"] == 0
        assert body["best_streak"] == 0
        assert body["last_completed"] is None

    def test_create_routine_linked_habit(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.post(
            "/api/habits",
            json={"title": "Stretch", "routine_id": routine["id"]},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["routine_id"] == routine["id"]
        assert body["frequency"] is None

    def test_create_routine_linked_habit_with_frequency(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.post(
            "/api/habits",
            json={
                "title": "Stretch",
                "routine_id": routine["id"],
                "frequency": "weekdays",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["frequency"] == "weekdays"

    def test_create_standalone_missing_frequency(self, client):
        resp = client.post(
            "/api/habits",
            json={"title": "No freq"},
        )
        assert resp.status_code == 422

    def test_create_with_optional_fields(self, client):
        resp = client.post(
            "/api/habits",
            json={
                "title": "Meditate",
                "frequency": "daily",
                "description": "10 min mindfulness",
                "notification_frequency": "daily",
                "scaffolding_status": "accountable",
                "introduced_at": "2026-04-01",
                "graduation_window": 60,
                "graduation_target": 0.9,
                "graduation_threshold": 45,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["description"] == "10 min mindfulness"
        assert body["notification_frequency"] == "daily"
        assert body["scaffolding_status"] == "accountable"
        assert body["introduced_at"] == "2026-04-01"
        assert body["graduation_window"] == 60
        assert body["graduation_target"] == 0.9
        assert body["graduation_threshold"] == 45

    def test_create_invalid_routine_id(self, client):
        resp = client.post(
            "/api/habits",
            json={"title": "Orphan", "routine_id": FAKE_UUID},
        )
        assert resp.status_code == 400

    def test_create_missing_title(self, client):
        resp = client.post(
            "/api/habits",
            json={"frequency": "daily"},
        )
        assert resp.status_code == 422

    def test_create_title_too_long(self, client):
        resp = client.post(
            "/api/habits",
            json={"title": "x" * 201, "frequency": "daily"},
        )
        assert resp.status_code == 422

    def test_create_invalid_frequency(self, client):
        resp = client.post(
            "/api/habits",
            json={"title": "Bad", "frequency": "INVALID"},
        )
        assert resp.status_code == 422

    def test_create_invalid_status(self, client):
        resp = client.post(
            "/api/habits",
            json={"title": "Bad", "frequency": "daily", "status": "INVALID"},
        )
        assert resp.status_code == 422

    def test_create_graduation_target_too_high(self, client):
        resp = client.post(
            "/api/habits",
            json={"title": "Bad", "frequency": "daily", "graduation_target": 1.5},
        )
        assert resp.status_code == 422

    def test_create_graduation_target_negative(self, client):
        resp = client.post(
            "/api/habits",
            json={"title": "Bad", "frequency": "daily", "graduation_target": -0.1},
        )
        assert resp.status_code == 422

    def test_create_graduation_target_boundary_values(self, client):
        resp_zero = client.post(
            "/api/habits",
            json={"title": "Zero", "frequency": "daily", "graduation_target": 0.0},
        )
        assert resp_zero.status_code == 201

        resp_one = client.post(
            "/api/habits",
            json={"title": "One", "frequency": "daily", "graduation_target": 1.0},
        )
        assert resp_one.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/habits
# ---------------------------------------------------------------------------


class TestListHabits:

    def test_list_habits_empty(self, client):
        resp = client.get("/api/habits")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_habits(self, client):
        make_habit(client, title="A")
        make_habit(client, title="B")
        resp = client.get("/api/habits")
        assert len(resp.json()) == 2

    def test_filter_by_routine_id(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        make_habit(client, title="Linked", routine_id=routine["id"])
        make_habit(client, title="Standalone")
        resp = client.get(f"/api/habits?routine_id={routine['id']}")
        habits = resp.json()
        assert len(habits) == 1
        assert habits[0]["title"] == "Linked"

    def test_filter_by_status(self, client):
        make_habit(client, title="Active", status="active")
        make_habit(client, title="Paused", status="paused")
        resp = client.get("/api/habits?status=paused")
        habits = resp.json()
        assert len(habits) == 1
        assert habits[0]["title"] == "Paused"

    def test_filter_by_scaffolding_status(self, client):
        make_habit(client, title="Tracking", scaffolding_status="tracking")
        make_habit(client, title="Accountable", scaffolding_status="accountable")
        resp = client.get("/api/habits?scaffolding_status=accountable")
        habits = resp.json()
        assert len(habits) == 1
        assert habits[0]["title"] == "Accountable"

    def test_filter_combined(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        make_habit(
            client, title="Match",
            routine_id=routine["id"], status="active",
            scaffolding_status="accountable",
        )
        make_habit(
            client, title="Wrong status",
            routine_id=routine["id"], status="paused",
            scaffolding_status="accountable",
        )
        make_habit(
            client, title="Wrong routine",
            status="active", scaffolding_status="accountable",
        )
        resp = client.get(
            f"/api/habits?routine_id={routine['id']}"
            "&status=active&scaffolding_status=accountable"
        )
        habits = resp.json()
        assert len(habits) == 1
        assert habits[0]["title"] == "Match"

    def test_list_ordered_by_created_at(self, client):
        make_habit(client, title="First")
        make_habit(client, title="Second")
        resp = client.get("/api/habits")
        titles = [h["title"] for h in resp.json()]
        assert titles == ["First", "Second"]


# ---------------------------------------------------------------------------
# GET /api/habits/{id}
# ---------------------------------------------------------------------------


class TestGetHabit:

    def test_get_habit_detail_standalone(self, client):
        habit = make_habit(client)
        resp = client.get(f"/api/habits/{habit['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == habit["title"]
        assert body["routine"] is None

    def test_get_habit_detail_with_routine(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        habit = make_habit(client, routine_id=routine["id"])
        resp = client.get(f"/api/habits/{habit['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["routine"] is not None
        assert body["routine"]["id"] == routine["id"]
        assert body["routine"]["title"] == routine["title"]

    def test_get_habit_not_found(self, client):
        resp = client.get(f"/api/habits/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/habits/{id}
# ---------------------------------------------------------------------------


class TestUpdateHabit:

    def test_patch_habit(self, client):
        habit = make_habit(client, title="Old")
        resp = client.patch(
            f"/api/habits/{habit['id']}", json={"title": "New"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    def test_patch_habit_partial(self, client):
        habit = make_habit(client, title="Keep", scaffolding_status="tracking")
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"scaffolding_status": "accountable"},
        )
        body = resp.json()
        assert body["title"] == "Keep"
        assert body["scaffolding_status"] == "accountable"

    def test_patch_attach_to_routine(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        habit = make_habit(client)
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"routine_id": routine["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["routine_id"] == routine["id"]

    def test_patch_detach_from_routine_with_frequency(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        habit = make_habit(
            client, routine_id=routine["id"], frequency="daily",
        )
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"routine_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["routine_id"] is None

    def test_patch_detach_with_frequency_in_payload(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        # Create habit under routine with no frequency
        habit = make_habit(client, routine_id=routine["id"], frequency=None)
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"routine_id": None, "frequency": "weekly"},
        )
        assert resp.status_code == 200
        assert resp.json()["routine_id"] is None
        assert resp.json()["frequency"] == "weekly"

    def test_patch_detach_without_frequency_fails(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        # Create habit under routine with no frequency
        habit = make_habit(client, routine_id=routine["id"], frequency=None)
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"routine_id": None},
        )
        assert resp.status_code == 422

    def test_patch_invalid_routine_id(self, client):
        habit = make_habit(client)
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"routine_id": FAKE_UUID},
        )
        assert resp.status_code == 400

    def test_patch_habit_not_found(self, client):
        resp = client.patch(f"/api/habits/{FAKE_UUID}", json={"title": "X"})
        assert resp.status_code == 404

    def test_patch_invalid_status(self, client):
        habit = make_habit(client)
        resp = client.patch(
            f"/api/habits/{habit['id']}", json={"status": "INVALID"},
        )
        assert resp.status_code == 422

    def test_patch_invalid_frequency(self, client):
        habit = make_habit(client)
        resp = client.patch(
            f"/api/habits/{habit['id']}", json={"frequency": "INVALID"},
        )
        assert resp.status_code == 422

    def test_patch_graduation_target_out_of_range(self, client):
        habit = make_habit(client)
        resp = client.patch(
            f"/api/habits/{habit['id']}", json={"graduation_target": 2.0},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/habits/{id}
# ---------------------------------------------------------------------------


class TestDeleteHabit:

    def test_delete_habit(self, client):
        habit = make_habit(client)
        resp = client.delete(f"/api/habits/{habit['id']}")
        assert resp.status_code == 204
        resp = client.get(f"/api/habits/{habit['id']}")
        assert resp.status_code == 404

    def test_delete_habit_not_found(self, client):
        resp = client.delete(f"/api/habits/{FAKE_UUID}")
        assert resp.status_code == 404
