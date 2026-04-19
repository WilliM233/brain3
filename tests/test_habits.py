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

from datetime import date

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
                "accountable_since": "2026-04-01",
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
        assert body["accountable_since"] == "2026-04-01"
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
        assert resp.json() == {"items": [], "count": 0}

    def test_list_habits_single(self, client):
        make_habit(client, title="Only")
        resp = client.get("/api/habits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Only"

    def test_list_habits(self, client):
        make_habit(client, title="A")
        make_habit(client, title="B")
        resp = client.get("/api/habits")
        data = resp.json()
        assert data["count"] == 2
        assert len(data["items"]) == 2

    def test_filter_by_routine_id(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        make_habit(client, title="Linked", routine_id=routine["id"])
        make_habit(client, title="Standalone")
        resp = client.get(f"/api/habits?routine_id={routine['id']}")
        data = resp.json()
        assert data["count"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Linked"

    def test_filter_by_status(self, client):
        make_habit(client, title="Active", status="active")
        make_habit(client, title="Paused", status="paused")
        resp = client.get("/api/habits?status=paused")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["title"] == "Paused"

    def test_filter_by_scaffolding_status(self, client):
        make_habit(client, title="Tracking", scaffolding_status="tracking")
        make_habit(client, title="Accountable", scaffolding_status="accountable")
        resp = client.get("/api/habits?scaffolding_status=accountable")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["title"] == "Accountable"

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
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["title"] == "Match"

    def test_list_ordered_by_created_at(self, client):
        make_habit(client, title="First")
        make_habit(client, title="Second")
        resp = client.get("/api/habits")
        titles = [h["title"] for h in resp.json()["items"]]
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
# [2A-Enh-01] effective_graduation_params composite field
# ---------------------------------------------------------------------------


class TestEffectiveGraduationParams:
    """Amendment 05: composite graduation params on habit read responses.

    Source labels `"override"` / `"friction_default"` come from spec
    Amendment 05. Pre-existing `graduation_status_endpoint` uses its own
    legacy `"per_habit"` label; that divergence is tracked under D8-X and
    deliberately not touched here.
    """

    def test_get_habit_friction_default_source(self, client):
        """No overrides, friction_score=3 → friction-tier defaults, source=friction_default."""
        habit = make_habit(client, friction_score=3)
        resp = client.get(f"/api/habits/{habit['id']}")
        assert resp.status_code == 200
        params = resp.json()["effective_graduation_params"]
        assert params == {
            "window_days": 45,
            "target_rate": 0.85,
            "threshold_days": 45,
            "source": "friction_default",
        }

    def test_get_habit_friction_default_with_null_friction(self, client):
        """No overrides, no friction_score → middle-tier defaults."""
        habit = make_habit(client)
        resp = client.get(f"/api/habits/{habit['id']}")
        params = resp.json()["effective_graduation_params"]
        assert params["source"] == "friction_default"
        assert params["window_days"] == 45
        assert params["target_rate"] == 0.85
        assert params["threshold_days"] == 45

    def test_get_habit_override_source_single_column(self, client):
        """Any single override column non-NULL → source=override."""
        habit = make_habit(client, friction_score=1, graduation_window=90)
        resp = client.get(f"/api/habits/{habit['id']}")
        params = resp.json()["effective_graduation_params"]
        assert params["source"] == "override"
        assert params["window_days"] == 90  # override
        assert params["target_rate"] == 0.85  # friction-1 default
        assert params["threshold_days"] == 30  # friction-1 default

    def test_get_habit_override_source_all_three_columns(self, client):
        """All three overrides set → source=override, values come from overrides."""
        habit = make_habit(
            client,
            friction_score=1,
            graduation_window=100,
            graduation_target=0.70,
            graduation_threshold=100,
        )
        resp = client.get(f"/api/habits/{habit['id']}")
        params = resp.json()["effective_graduation_params"]
        assert params == {
            "window_days": 100,
            "target_rate": 0.70,
            "threshold_days": 100,
            "source": "override",
        }

    def test_get_habit_applies_re_scaffold_tightening_friction_default(self, db, client):
        """re_scaffold_count>0 tightens values — source stays friction_default."""
        import uuid

        from app.models import Habit

        habit = Habit(
            id=uuid.uuid4(),
            title="Tightened habit",
            frequency="daily",
            status="active",
            scaffolding_status="tracking",
            friction_score=1,  # baseline defaults: (30, 0.85, 30)
            re_scaffold_count=2,
        )
        db.add(habit)
        db.commit()

        resp = client.get(f"/api/habits/{habit.id}")
        params = resp.json()["effective_graduation_params"]
        # Double re-scaffold from (30, 0.85, 30): (37, 0.90, 37) → (46, 0.95, 46)
        assert params == {
            "window_days": 46,
            "target_rate": 0.95,
            "threshold_days": 46,
            "source": "friction_default",
        }

    def test_get_habit_re_scaffold_tightens_overrides(self, db, client):
        """Tightening applies to override baseline; source stays override."""
        import uuid

        from app.models import Habit

        habit = Habit(
            id=uuid.uuid4(),
            title="Tightened override",
            frequency="daily",
            status="active",
            scaffolding_status="tracking",
            graduation_window=60,
            graduation_target=0.70,
            graduation_threshold=60,
            re_scaffold_count=1,
        )
        db.add(habit)
        db.commit()

        resp = client.get(f"/api/habits/{habit.id}")
        params = resp.json()["effective_graduation_params"]
        # Single re-scaffold from (60, 0.70, 60): (75, 0.75, 75)
        assert params["window_days"] == 75
        assert params["target_rate"] == 0.75
        assert params["threshold_days"] == 75
        assert params["source"] == "override"

    def test_list_habits_items_include_effective_graduation_params(self, client):
        """Each item in GET /api/habits includes effective_graduation_params."""
        make_habit(client, title="H1", friction_score=1)
        make_habit(
            client,
            title="H2",
            friction_score=5,
            graduation_window=100,
        )
        resp = client.get("/api/habits")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        for item in body["items"]:
            assert "effective_graduation_params" in item
            assert set(item["effective_graduation_params"].keys()) == {
                "window_days",
                "target_rate",
                "threshold_days",
                "source",
            }
        sources = {
            item["title"]: item["effective_graduation_params"]["source"]
            for item in body["items"]
        }
        assert sources["H1"] == "friction_default"
        assert sources["H2"] == "override"

    def test_effective_graduation_params_ignored_in_post_body(self, client):
        """Request-body effective_graduation_params is ignored; response reflects computed value."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Ignored field",
                "frequency": "daily",
                "friction_score": 1,
                "effective_graduation_params": {
                    "window_days": 999,
                    "target_rate": 0.01,
                    "threshold_days": 999,
                    "source": "override",
                },
            },
        )
        assert resp.status_code == 201
        params = resp.json()["effective_graduation_params"]
        # Computed from friction_score=1 with no overrides — NOT echoed
        assert params == {
            "window_days": 30,
            "target_rate": 0.85,
            "threshold_days": 30,
            "source": "friction_default",
        }

    def test_effective_graduation_params_ignored_in_patch_body(self, client):
        """PATCH body cannot set effective_graduation_params — it stays computed."""
        habit = make_habit(client, friction_score=3)
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={
                "effective_graduation_params": {
                    "window_days": 1,
                    "target_rate": 0.01,
                    "threshold_days": 1,
                    "source": "override",
                },
            },
        )
        assert resp.status_code == 200
        params = resp.json()["effective_graduation_params"]
        # friction_score=3 defaults still apply
        assert params == {
            "window_days": 45,
            "target_rate": 0.85,
            "threshold_days": 45,
            "source": "friction_default",
        }


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
# [2G-Gap-01] Auto-populate accountable_since on transition to accountable
# ---------------------------------------------------------------------------


class TestIntroducedAtAutoPopulate:

    def test_create_accountable_without_accountable_since_sets_today(self, client):
        """POST with scaffolding_status=accountable and no accountable_since → today."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Meditate",
                "frequency": "daily",
                "scaffolding_status": "accountable",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["accountable_since"] == date.today().isoformat()

    def test_create_accountable_with_explicit_accountable_since_respected(self, client):
        """POST with explicit accountable_since is never overwritten."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Meditate",
                "frequency": "daily",
                "scaffolding_status": "accountable",
                "accountable_since": "2026-01-15",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["accountable_since"] == "2026-01-15"

    def test_create_tracking_leaves_accountable_since_null(self, client):
        """POST with scaffolding_status=tracking does not auto-set accountable_since."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Journal",
                "frequency": "daily",
                "scaffolding_status": "tracking",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["accountable_since"] is None

    def test_patch_transition_to_accountable_sets_today(self, client):
        """PATCH transition tracking → accountable with no prior value → today."""
        habit = make_habit(client, scaffolding_status="tracking")
        assert habit["accountable_since"] is None

        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"scaffolding_status": "accountable"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["scaffolding_status"] == "accountable"
        assert body["accountable_since"] == date.today().isoformat()

    def test_patch_transition_with_explicit_accountable_since_respected(self, client):
        """PATCH transition with explicit accountable_since uses the provided value."""
        habit = make_habit(client, scaffolding_status="tracking")
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={
                "scaffolding_status": "accountable",
                "accountable_since": "2026-03-01",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["accountable_since"] == "2026-03-01"

    def test_patch_unchanged_scaffolding_does_not_touch_accountable_since(self, client):
        """PATCH that doesn't change scaffolding_status never modifies accountable_since."""
        habit = make_habit(client, scaffolding_status="tracking")
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"title": "Rename only"},
        )
        assert resp.status_code == 200
        assert resp.json()["accountable_since"] is None

    def test_patch_already_accountable_with_value_not_overwritten(self, client):
        """PATCH on a habit already accountable with accountable_since set never mutates it."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Meditate",
                "frequency": "daily",
                "scaffolding_status": "accountable",
                "accountable_since": "2026-02-20",
            },
        )
        assert resp.status_code == 201
        habit = resp.json()

        # PATCH something unrelated — accountable_since must survive untouched.
        resp = client.patch(
            f"/api/habits/{habit['id']}", json={"title": "Meditate (renamed)"},
        )
        assert resp.status_code == 200
        assert resp.json()["accountable_since"] == "2026-02-20"

        # Re-sending scaffolding_status=accountable on a habit already at that
        # value + with a date set must also leave the date unchanged.
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"scaffolding_status": "accountable"},
        )
        assert resp.status_code == 200
        assert resp.json()["accountable_since"] == "2026-02-20"


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


# ---------------------------------------------------------------------------
# POST /api/habits/{id}/complete
# ---------------------------------------------------------------------------


class TestCompleteHabit:

    def test_complete_standalone_habit(self, client):
        """Happy path — complete a standalone daily habit."""
        habit = make_habit(client, frequency="daily")
        resp = client.post(f"/api/habits/{habit['id']}/complete")
        assert resp.status_code == 200
        data = resp.json()
        assert data["habit_id"] == habit["id"]
        assert data["completion_id"] is not None
        assert data["current_streak"] == 1
        assert data["best_streak"] == 1
        assert data["streak_was_broken"] is False
        assert data["source"] == "individual"

    def test_complete_routine_linked_habit_no_cascade(self, client):
        """Completing a routine-linked habit does NOT complete the routine."""
        domain = make_domain(client)
        routine = make_routine(client, domain["id"], frequency="daily")
        habit = make_habit(client, routine_id=routine["id"], frequency=None)

        resp = client.post(f"/api/habits/{habit['id']}/complete")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_streak"] == 1

        # Routine streak should be untouched
        routine_resp = client.get(f"/api/routines/{routine['id']}")
        assert routine_resp.json()["current_streak"] == 0

    def test_complete_habit_frequency_fallback_to_routine(self, client):
        """Habit without own frequency resolves from parent routine."""
        domain = make_domain(client)
        routine = make_routine(client, domain["id"], frequency="weekly")
        habit = make_habit(client, routine_id=routine["id"], frequency=None)

        resp = client.post(f"/api/habits/{habit['id']}/complete")
        assert resp.status_code == 200
        assert resp.json()["current_streak"] == 1

    def test_complete_with_backdating(self, client):
        """Backdating via completed_date field works."""
        habit = make_habit(client, frequency="daily")
        resp = client.post(
            f"/api/habits/{habit['id']}/complete",
            json={"completed_date": "2026-04-01"},
        )
        assert resp.status_code == 200
        assert resp.json()["completed_date"] == "2026-04-01"

    def test_complete_with_notes(self, client):
        """Notes field is accepted and stored."""
        habit = make_habit(client, frequency="daily")
        resp = client.post(
            f"/api/habits/{habit['id']}/complete",
            json={"notes": "Felt great today!"},
        )
        assert resp.status_code == 200
        assert resp.json()["completion_id"] is not None

    def test_complete_idempotent_same_day(self, client):
        """Same habit + same date returns existing record, no duplicate."""
        habit = make_habit(client, frequency="daily")
        resp1 = client.post(
            f"/api/habits/{habit['id']}/complete",
            json={"completed_date": "2026-04-10"},
        )
        resp2 = client.post(
            f"/api/habits/{habit['id']}/complete",
            json={"completed_date": "2026-04-10"},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["completion_id"] == resp2.json()["completion_id"]

    def test_complete_paused_habit_rejected(self, client):
        """Paused habits cannot be completed."""
        habit = make_habit(client, frequency="daily")
        client.patch(f"/api/habits/{habit['id']}", json={"status": "paused"})
        resp = client.post(f"/api/habits/{habit['id']}/complete")
        assert resp.status_code == 400
        assert "paused" in resp.json()["detail"]

    def test_complete_graduated_habit_rejected(self, client):
        """Graduated habits cannot be completed."""
        habit = make_habit(client, frequency="daily")
        client.patch(f"/api/habits/{habit['id']}", json={"status": "graduated"})
        resp = client.post(f"/api/habits/{habit['id']}/complete")
        assert resp.status_code == 400
        assert "graduated" in resp.json()["detail"]

    def test_complete_abandoned_habit_rejected(self, client):
        """Abandoned habits cannot be completed."""
        habit = make_habit(client, frequency="daily")
        client.patch(f"/api/habits/{habit['id']}", json={"status": "abandoned"})
        resp = client.post(f"/api/habits/{habit['id']}/complete")
        assert resp.status_code == 400
        assert "abandoned" in resp.json()["detail"]

    def test_complete_not_found(self, client):
        """404 for invalid habit UUID."""
        resp = client.post(f"/api/habits/{FAKE_UUID}/complete")
        assert resp.status_code == 404

    def test_streak_builds_consecutively(self, client):
        """Streak increments on consecutive daily completions."""
        habit = make_habit(client, frequency="daily")
        client.post(
            f"/api/habits/{habit['id']}/complete",
            json={"completed_date": "2026-04-10"},
        )
        resp = client.post(
            f"/api/habits/{habit['id']}/complete",
            json={"completed_date": "2026-04-11"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_streak"] == 2
        assert data["best_streak"] == 2
        assert data["streak_was_broken"] is False

    def test_streak_breaks_on_gap(self, client):
        """Streak resets when gap exceeds frequency tolerance."""
        habit = make_habit(client, frequency="daily")
        client.post(
            f"/api/habits/{habit['id']}/complete",
            json={"completed_date": "2026-04-10"},
        )
        resp = client.post(
            f"/api/habits/{habit['id']}/complete",
            json={"completed_date": "2026-04-13"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_streak"] == 1
        assert data["best_streak"] == 1
        assert data["streak_was_broken"] is True
