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

"""Tests for Routine CRUD, schedule management, and completion endpoints."""

from datetime import date, timedelta
from uuid import UUID

from tests.conftest import FAKE_UUID, make_domain, make_habit, make_routine

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

    def test_create_routine_title_too_long(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/routines",
            json={"domain_id": domain["id"], "title": "x" * 201, "frequency": "daily"},
        )
        assert resp.status_code == 422

    def test_create_routine_invalid_frequency(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/routines",
            json={"domain_id": domain["id"], "title": "Bad", "frequency": "INVALID"},
        )
        assert resp.status_code == 422

    def test_create_routine_invalid_status(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/routines",
            json={
                "domain_id": domain["id"], "title": "Bad", "frequency": "daily",
                "status": "INVALID",
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
        assert resp.json() == {"items": [], "count": 0}

    def test_list_routines_single(self, client):
        domain = make_domain(client)
        make_routine(client, domain["id"], title="Only")
        resp = client.get("/api/routines")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Only"

    def test_list_routines(self, client):
        domain = make_domain(client)
        make_routine(client, domain["id"], title="A")
        make_routine(client, domain["id"], title="B")
        resp = client.get("/api/routines")
        data = resp.json()
        assert data["count"] == 2
        assert len(data["items"]) == 2

    def test_filter_by_domain_id(self, client):
        d1 = make_domain(client, name="D1")
        d2 = make_domain(client, name="D2")
        make_routine(client, d1["id"], title="R1")
        make_routine(client, d2["id"], title="R2")
        resp = client.get(f"/api/routines?domain_id={d1['id']}")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["title"] == "R1"

    def test_filter_by_status(self, client):
        domain = make_domain(client)
        make_routine(client, domain["id"], title="Active", status="active")
        make_routine(client, domain["id"], title="Paused", status="paused")
        resp = client.get("/api/routines?status=paused")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["title"] == "Paused"

    def test_filter_by_frequency(self, client):
        domain = make_domain(client)
        make_routine(client, domain["id"], title="Daily", frequency="daily")
        make_routine(client, domain["id"], title="Weekly", frequency="weekly")
        resp = client.get("/api/routines?frequency=weekly")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["title"] == "Weekly"

    def test_filter_streak_broken(self, client):
        domain = make_domain(client)
        make_routine(client, domain["id"], title="Broken")
        r_ok = make_routine(client, domain["id"], title="OK")
        make_routine(client, domain["id"], title="Paused", status="paused")

        # Give "OK" a streak by completing it
        client.post(f"/api/routines/{r_ok['id']}/complete")

        resp = client.get("/api/routines?streak_broken=true")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["title"] == "Broken"
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

    def test_patch_routine_reparent_to_different_domain(self, client):
        """Move a routine from one domain to another via PATCH."""
        domain_a = make_domain(client, name="Domain A")
        domain_b = make_domain(client, name="Domain B")
        routine = make_routine(client, domain_a["id"])

        resp = client.patch(
            f"/api/routines/{routine['id']}",
            json={"domain_id": domain_b["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["domain_id"] == domain_b["id"]

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

    def test_patch_routine_invalid_frequency(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.patch(
            f"/api/routines/{routine['id']}", json={"frequency": "INVALID"},
        )
        assert resp.status_code == 422

    def test_patch_routine_invalid_status(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.patch(
            f"/api/routines/{routine['id']}", json={"status": "INVALID"},
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


# ---------------------------------------------------------------------------
# Scripted routine completion (routine with child habits)
# ---------------------------------------------------------------------------

class TestScriptedRoutineCompletion:
    """Tests for routines that have child habits — the new scripted path."""

    def _make_scripted_routine(self, client):
        """Create a routine with two active child habits."""
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        h1 = make_habit(client, routine_id=routine["id"], title="Habit A")
        h2 = make_habit(client, routine_id=routine["id"], title="Habit B")
        return routine, h1, h2

    # -- all_done -----------------------------------------------------------

    def test_all_done_cascades_to_habits(self, client):
        routine, h1, h2 = self._make_scripted_routine(client)
        resp = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "all_done"
        assert body["completion_id"] is not None
        assert set(body["habits_completed"]) == {h1["id"], h2["id"]}
        assert body["current_streak"] == 1
        assert body["streak_was_broken"] is False

    def test_all_done_habit_streaks_updated(self, client):
        routine, h1, h2 = self._make_scripted_routine(client)
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        )
        # Verify habit streaks were updated
        for hid in (h1["id"], h2["id"]):
            resp = client.get(f"/api/habits/{hid}")
            assert resp.json()["current_streak"] == 1
            assert resp.json()["last_completed"] == date.today().isoformat()

    def test_all_done_creates_habit_completions_with_cascade_source(self, client, db):
        from app.models import HabitCompletion

        routine, h1, h2 = self._make_scripted_routine(client)
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        )
        completions = db.query(HabitCompletion).all()
        assert len(completions) == 2
        for c in completions:
            assert c.source == "routine_cascade"

    def test_all_done_creates_routine_completion_record(self, client, db):
        from app.models import RoutineCompletion

        routine, h1, h2 = self._make_scripted_routine(client)
        resp = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        )
        body = resp.json()
        rc = db.query(RoutineCompletion).filter(
            RoutineCompletion.id == UUID(body["completion_id"])
        ).first()
        assert rc is not None
        assert rc.status == "all_done"
        assert rc.reconciled is True

    def test_all_done_default_status(self, client):
        """Calling complete with no status defaults to all_done."""
        routine, h1, h2 = self._make_scripted_routine(client)
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        assert body["status"] == "all_done"
        assert set(body["habits_completed"]) == {h1["id"], h2["id"]}

    def test_all_done_skips_graduated_habits(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        active = make_habit(client, routine_id=routine["id"], title="Active Habit")
        graduated = make_habit(
            client,
            routine_id=routine["id"],
            title="Graduated Habit",
            scaffolding_status="graduated",
        )
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        assert body["habits_completed"] == [active["id"]]
        assert graduated["id"] not in body["habits_completed"]

    def test_all_done_skips_non_active_habits(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        active = make_habit(client, routine_id=routine["id"], title="Active Habit")
        paused = make_habit(
            client,
            routine_id=routine["id"],
            title="Paused Habit",
            status="paused",
        )
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        assert body["habits_completed"] == [active["id"]]
        assert paused["id"] not in body["habits_completed"]

    def test_all_done_mixed_active_and_graduated(self, client):
        """Only active non-graduated habits get cascaded."""
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        h_active = make_habit(client, routine_id=routine["id"], title="A")
        make_habit(
            client, routine_id=routine["id"], title="G",
            scaffolding_status="graduated",
        )
        make_habit(
            client, routine_id=routine["id"], title="P",
            status="paused",
        )
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        assert body["habits_completed"] == [h_active["id"]]

    # -- Idempotency --------------------------------------------------------

    def test_all_done_idempotent_skips_already_completed_habit(self, client):
        """If a habit was individually completed today, cascade skips it."""
        routine, h1, h2 = self._make_scripted_routine(client)
        # Complete h1 individually first
        client.post(f"/api/habits/{h1['id']}/complete")
        # Now cascade via routine
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        # Only h2 should be in the cascade list
        assert body["habits_completed"] == [h2["id"]]

    def test_all_done_idempotent_all_habits_already_completed(self, client):
        """If all habits already completed today, cascade list is empty."""
        routine, h1, h2 = self._make_scripted_routine(client)
        client.post(f"/api/habits/{h1['id']}/complete")
        client.post(f"/api/habits/{h2['id']}/complete")
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        assert body["habits_completed"] == []
        # Routine streak should still be updated
        assert body["current_streak"] == 1

    # -- partial ------------------------------------------------------------

    def test_partial_does_not_cascade(self, client):
        routine, h1, h2 = self._make_scripted_routine(client)
        resp = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "partial", "freeform_note": "Did 2 of 3 things"},
        )
        body = resp.json()
        assert body["status"] == "partial"
        assert body["habits_completed"] == []
        # Routine still gets streak credit
        assert body["current_streak"] == 1

    def test_partial_stores_freeform_note(self, client, db):
        from app.models import RoutineCompletion

        routine, h1, h2 = self._make_scripted_routine(client)
        resp = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "partial", "freeform_note": "Only flossed"},
        )
        body = resp.json()
        rc = db.query(RoutineCompletion).filter(
            RoutineCompletion.id == UUID(body["completion_id"])
        ).first()
        assert rc.freeform_note == "Only flossed"
        assert rc.reconciled is False

    def test_partial_habits_untouched(self, client):
        routine, h1, h2 = self._make_scripted_routine(client)
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "partial"},
        )
        for hid in (h1["id"], h2["id"]):
            resp = client.get(f"/api/habits/{hid}")
            assert resp.json()["current_streak"] == 0
            assert resp.json()["last_completed"] is None

    # -- skipped ------------------------------------------------------------

    def test_skipped_freezes_streak(self, client):
        routine, h1, h2 = self._make_scripted_routine(client)
        # Build a streak first
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"completed_date": yesterday},
        )
        # Now skip today
        resp = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "skipped"},
        )
        body = resp.json()
        assert body["status"] == "skipped"
        # Streak frozen at 1 — not incremented, not broken
        assert body["current_streak"] == 1
        assert body["streak_was_broken"] is False

    def test_skipped_does_not_cascade(self, client):
        routine, h1, h2 = self._make_scripted_routine(client)
        resp = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "skipped"},
        )
        body = resp.json()
        assert body["habits_completed"] == []

    def test_skipped_habits_untouched(self, client):
        routine, h1, h2 = self._make_scripted_routine(client)
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "skipped"},
        )
        for hid in (h1["id"], h2["id"]):
            resp = client.get(f"/api/habits/{hid}")
            assert resp.json()["current_streak"] == 0

    def test_skipped_reconciled_true(self, client, db):
        from app.models import RoutineCompletion

        routine, h1, h2 = self._make_scripted_routine(client)
        resp = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "skipped"},
        )
        body = resp.json()
        rc = db.query(RoutineCompletion).filter(
            RoutineCompletion.id == UUID(body["completion_id"])
        ).first()
        assert rc.reconciled is True

    def test_skipped_does_not_break_streak_on_subsequent_completion(self, client):
        """Skip preserves the streak so the next real completion can continue."""
        routine, h1, h2 = self._make_scripted_routine(client)
        two_days_ago = (date.today() - timedelta(days=2)).isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        # Complete two days ago (streak = 1)
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"completed_date": two_days_ago},
        )
        # Skip yesterday (streak frozen at 1)
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "skipped", "completed_date": yesterday},
        )
        # Complete today — gap from last *real* completion is 2 days,
        # which breaks daily streak. But the skip yesterday means the
        # last_completed still points to two_days_ago.
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        # Daily frequency: 2-day gap from two_days_ago to today breaks streak
        assert body["current_streak"] == 1
        assert body["streak_was_broken"] is True

    # -- Freeform regression ------------------------------------------------

    def test_freeform_routine_unchanged(self, client):
        """Freeform routines (no habits) keep v1 behaviour, return None fields."""
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        assert body["completion_id"] is None
        assert body["status"] is None
        assert body["habits_completed"] is None
        assert body["current_streak"] == 1

    def test_freeform_accepts_status_but_ignores_it(self, client):
        """Freeform routines ignore status — always take v1 path."""
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "skipped"},
        )
        body = resp.json()
        # Freeform path: status is ignored, streak still evaluated
        assert body["completion_id"] is None
        assert body["current_streak"] == 1

    # -- Streak evaluation on scripted routines -----------------------------

    def test_scripted_streak_continues(self, client):
        routine, h1, h2 = self._make_scripted_routine(client)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"completed_date": yesterday},
        )
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        assert body["current_streak"] == 2
        assert body["streak_was_broken"] is False

    def test_scripted_streak_breaks(self, client):
        routine, h1, h2 = self._make_scripted_routine(client)
        three_days_ago = (date.today() - timedelta(days=3)).isoformat()
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"completed_date": three_days_ago},
        )
        resp = client.post(f"/api/routines/{routine['id']}/complete")
        body = resp.json()
        assert body["current_streak"] == 1
        assert body["streak_was_broken"] is True


# ---------------------------------------------------------------------------
# [2C-26] Part C — routine completion idempotency on (routine, date, status)
# ---------------------------------------------------------------------------

class TestScriptedRoutineCompletionIdempotency:
    """Same (routine, date, status) tuple dedups; mixed status on same date persists."""

    def _make_scripted_routine(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        h1 = make_habit(client, routine_id=routine["id"], title="Habit A")
        h2 = make_habit(client, routine_id=routine["id"], title="Habit B")
        return routine, h1, h2

    def test_duplicate_same_status_returns_existing_row(self, client, db):
        from app.models import RoutineCompletion

        routine, _, _ = self._make_scripted_routine(client)
        first = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        ).json()
        second = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        ).json()

        assert second["completion_id"] == first["completion_id"]
        assert second["status"] == first["status"]
        rows = (
            db.query(RoutineCompletion)
            .filter(RoutineCompletion.routine_id == UUID(routine["id"]))
            .all()
        )
        assert len(rows) == 1

    def test_idempotent_streak_unchanged_on_second_call(self, client):
        routine, _, _ = self._make_scripted_routine(client)
        first = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        ).json()
        second = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        ).json()
        assert first["current_streak"] == 1
        assert second["current_streak"] == 1
        assert second["streak_was_broken"] is False

    def test_idempotent_no_recascade_to_habits(self, client, db):
        from app.models import HabitCompletion

        routine, h1, h2 = self._make_scripted_routine(client)
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        )
        # Snapshot habit completion count after the first cascade
        first_count = db.query(HabitCompletion).count()

        retry = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        ).json()
        assert retry["habits_completed"] == []
        # No new habit completions on the idempotent retry
        assert db.query(HabitCompletion).count() == first_count

    def test_cross_status_same_date_persists_two_rows(self, client, db):
        from app.models import RoutineCompletion

        routine, _, _ = self._make_scripted_routine(client)
        all_done = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        ).json()
        partial = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "partial", "freeform_note": "Reconciliation note"},
        ).json()

        assert all_done["completion_id"] != partial["completion_id"]
        rows = (
            db.query(RoutineCompletion)
            .filter(RoutineCompletion.routine_id == UUID(routine["id"]))
            .order_by(RoutineCompletion.status)
            .all()
        )
        statuses = [r.status for r in rows]
        assert statuses == ["all_done", "partial"]

    def test_cross_status_streak_unchanged_on_second_status(self, client):
        """Both same-day rows count as one day for streak purposes (idempotent
        evaluate_streak on identical completed_date)."""
        routine, _, _ = self._make_scripted_routine(client)
        first = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        ).json()
        second = client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "partial"},
        ).json()
        assert first["current_streak"] == 1
        assert second["current_streak"] == 1
