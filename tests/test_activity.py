"""Tests for Activity Log CRUD endpoints."""

from datetime import datetime, timezone

from app.models import ActivityLog
from tests.conftest import (
    FAKE_UUID,
    make_activity,
    make_checkin,
    make_domain,
    make_routine,
    make_task,
)

# ---------------------------------------------------------------------------
# POST /api/activity
# ---------------------------------------------------------------------------

class TestCreateActivity:

    def test_create_standalone(self, client):
        resp = client.post(
            "/api/activity",
            json={"action_type": "reflected", "notes": "Good day overall"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["action_type"] == "reflected"
        assert body["notes"] == "Good day overall"
        assert body["task_id"] is None
        assert body["logged_at"] is not None

    def test_create_with_task(self, client):
        task = make_task(client, title="Buy milk")
        resp = client.post(
            "/api/activity",
            json={
                "task_id": task["id"],
                "action_type": "completed",
                "energy_before": 3,
                "energy_after": 2,
                "friction_actual": 1,
                "duration_minutes": 15,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["task_id"] == task["id"]
        assert body["energy_before"] == 3
        assert body["energy_after"] == 2

    def test_create_with_routine(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.post(
            "/api/activity",
            json={"routine_id": routine["id"], "action_type": "completed"},
        )
        assert resp.status_code == 201
        assert resp.json()["routine_id"] == routine["id"]

    def test_create_with_checkin(self, client):
        checkin = make_checkin(client)
        resp = client.post(
            "/api/activity",
            json={"checkin_id": checkin["id"], "action_type": "checked_in"},
        )
        assert resp.status_code == 201
        assert resp.json()["checkin_id"] == checkin["id"]

    def test_create_multiple_refs_rejected(self, client):
        task = make_task(client)
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        resp = client.post(
            "/api/activity",
            json={
                "task_id": task["id"],
                "routine_id": routine["id"],
                "action_type": "completed",
            },
        )
        assert resp.status_code == 422

    def test_create_invalid_task_ref(self, client):
        resp = client.post(
            "/api/activity",
            json={"task_id": FAKE_UUID, "action_type": "completed"},
        )
        assert resp.status_code == 400

    def test_create_invalid_routine_ref(self, client):
        resp = client.post(
            "/api/activity",
            json={"routine_id": FAKE_UUID, "action_type": "completed"},
        )
        assert resp.status_code == 400

    def test_create_invalid_checkin_ref(self, client):
        resp = client.post(
            "/api/activity",
            json={"checkin_id": FAKE_UUID, "action_type": "checked_in"},
        )
        assert resp.status_code == 400

    def test_create_missing_action_type(self, client):
        resp = client.post("/api/activity", json={"notes": "Hello"})
        assert resp.status_code == 422

    def test_create_invalid_energy_scale(self, client):
        resp = client.post(
            "/api/activity",
            json={"action_type": "completed", "energy_before": 6},
        )
        assert resp.status_code == 422

    def test_create_invalid_mood_scale(self, client):
        resp = client.post(
            "/api/activity",
            json={"action_type": "completed", "mood_rating": 0},
        )
        assert resp.status_code == 422

    def test_create_notes_too_long(self, client):
        resp = client.post(
            "/api/activity",
            json={"action_type": "reflected", "notes": "x" * 5001},
        )
        assert resp.status_code == 422

    def test_create_invalid_action_type(self, client):
        resp = client.post(
            "/api/activity",
            json={"action_type": "INVALID"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/activity
# ---------------------------------------------------------------------------

class TestListActivity:

    def test_list_empty(self, client):
        resp = client.get("/api/activity")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        make_activity(client, action_type="completed")
        make_activity(client, action_type="reflected")
        resp = client.get("/api/activity")
        assert len(resp.json()) == 2

    def test_filter_by_action_type(self, client):
        make_activity(client, action_type="completed")
        make_activity(client, action_type="skipped")
        resp = client.get("/api/activity?action_type=skipped")
        entries = resp.json()
        assert len(entries) == 1
        assert entries[0]["action_type"] == "skipped"

    def test_filter_by_task_id(self, client):
        task = make_task(client)
        make_activity(client, task_id=task["id"])
        make_activity(client, action_type="reflected")
        resp = client.get(f"/api/activity?task_id={task['id']}")
        assert len(resp.json()) == 1

    def test_filter_by_routine_id(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        make_activity(client, routine_id=routine["id"])
        make_activity(client, action_type="reflected")
        resp = client.get(f"/api/activity?routine_id={routine['id']}")
        assert len(resp.json()) == 1

    def test_filter_logged_after(self, client):
        make_activity(client)
        resp = client.get("/api/activity?logged_after=2020-01-01T00:00:00")
        assert len(resp.json()) == 1

    def test_filter_logged_before(self, client):
        make_activity(client)
        resp = client.get("/api/activity?logged_before=2099-12-31T23:59:59")
        assert len(resp.json()) == 1

    def test_filter_composable_date_range(self, client):
        make_activity(client)
        resp = client.get(
            "/api/activity?logged_after=2020-01-01T00:00:00"
            "&logged_before=2099-12-31T23:59:59"
        )
        assert len(resp.json()) == 1

    def test_filter_has_task(self, client):
        task = make_task(client)
        make_activity(client, task_id=task["id"])
        make_activity(client, action_type="reflected")
        resp = client.get("/api/activity?has_task=true")
        assert len(resp.json()) == 1

    def test_filter_has_task_false(self, client):
        task = make_task(client)
        make_activity(client, task_id=task["id"])
        make_activity(client, action_type="reflected")
        resp = client.get("/api/activity?has_task=false")
        assert len(resp.json()) == 1
        assert resp.json()[0]["task_id"] is None

    def test_filter_has_routine(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        make_activity(client, routine_id=routine["id"])
        make_activity(client, action_type="reflected")
        resp = client.get("/api/activity?has_routine=true")
        assert len(resp.json()) == 1

    def test_reverse_chronological_order(self, client, db):
        early = ActivityLog(
            action_type="completed",
            logged_at=datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc),
        )
        late = ActivityLog(
            action_type="reflected",
            logged_at=datetime(2026, 3, 1, 20, 0, tzinfo=timezone.utc),
        )
        db.add_all([early, late])
        db.commit()
        resp = client.get("/api/activity")
        entries = resp.json()
        assert entries[0]["action_type"] == "reflected"
        assert entries[1]["action_type"] == "completed"


# ---------------------------------------------------------------------------
# GET /api/activity/{id}
# ---------------------------------------------------------------------------

class TestGetActivity:

    def test_get_detail_with_task(self, client):
        task = make_task(client, title="Buy milk")
        entry = make_activity(client, task_id=task["id"])
        resp = client.get(f"/api/activity/{entry['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["task"]["title"] == "Buy milk"
        assert body["routine"] is None
        assert body["checkin"] is None

    def test_get_detail_with_routine(self, client):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"], title="Morning walk")
        entry = make_activity(client, routine_id=routine["id"])
        resp = client.get(f"/api/activity/{entry['id']}")
        assert resp.json()["routine"]["title"] == "Morning walk"

    def test_get_detail_with_checkin(self, client):
        checkin = make_checkin(client, checkin_type="morning")
        entry = make_activity(client, checkin_id=checkin["id"], action_type="checked_in")
        resp = client.get(f"/api/activity/{entry['id']}")
        assert resp.json()["checkin"]["checkin_type"] == "morning"

    def test_get_detail_standalone(self, client):
        entry = make_activity(client, action_type="reflected")
        resp = client.get(f"/api/activity/{entry['id']}")
        body = resp.json()
        assert body["task"] is None
        assert body["routine"] is None
        assert body["checkin"] is None

    def test_get_not_found(self, client):
        resp = client.get(f"/api/activity/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/activity/{id}
# ---------------------------------------------------------------------------

class TestUpdateActivity:

    def test_patch_activity(self, client):
        entry = make_activity(client, notes="Old")
        resp = client.patch(
            f"/api/activity/{entry['id']}", json={"notes": "New"},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "New"

    def test_patch_partial(self, client):
        entry = make_activity(client, energy_before=3, mood_rating=2)
        resp = client.patch(
            f"/api/activity/{entry['id']}", json={"energy_before": 5},
        )
        body = resp.json()
        assert body["energy_before"] == 5
        assert body["mood_rating"] == 2

    def test_patch_not_found(self, client):
        resp = client.patch(f"/api/activity/{FAKE_UUID}", json={"notes": "X"})
        assert resp.status_code == 404

    def test_patch_invalid_scale(self, client):
        entry = make_activity(client)
        resp = client.patch(
            f"/api/activity/{entry['id']}", json={"friction_actual": 10},
        )
        assert resp.status_code == 422

    def test_patch_invalid_action_type(self, client):
        entry = make_activity(client)
        resp = client.patch(
            f"/api/activity/{entry['id']}", json={"action_type": "INVALID"},
        )
        assert resp.status_code == 422

    def test_patch_multiple_refs_rejected(self, client):
        """Adding a second reference to an entry with an existing one is rejected."""
        task = make_task(client)
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        entry = make_activity(client, task_id=task["id"])
        resp = client.patch(
            f"/api/activity/{entry['id']}", json={"routine_id": routine["id"]},
        )
        assert resp.status_code == 422

    def test_patch_replace_ref_allowed(self, client):
        """Clearing old ref and setting a new one in the same PATCH is allowed."""
        task = make_task(client)
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        entry = make_activity(client, task_id=task["id"])
        resp = client.patch(
            f"/api/activity/{entry['id']}",
            json={"task_id": None, "routine_id": routine["id"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] is None
        assert body["routine_id"] == routine["id"]

    def test_patch_invalid_task_ref(self, client):
        entry = make_activity(client)
        resp = client.patch(
            f"/api/activity/{entry['id']}", json={"task_id": FAKE_UUID},
        )
        assert resp.status_code == 400

    def test_patch_invalid_routine_ref(self, client):
        entry = make_activity(client)
        resp = client.patch(
            f"/api/activity/{entry['id']}", json={"routine_id": FAKE_UUID},
        )
        assert resp.status_code == 400

    def test_patch_invalid_checkin_ref(self, client):
        entry = make_activity(client)
        resp = client.patch(
            f"/api/activity/{entry['id']}", json={"checkin_id": FAKE_UUID},
        )
        assert resp.status_code == 400

    def test_patch_clear_ref_allowed(self, client):
        """Setting a ref to null should not trigger existence validation."""
        task = make_task(client)
        entry = make_activity(client, task_id=task["id"])
        resp = client.patch(
            f"/api/activity/{entry['id']}", json={"task_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["task_id"] is None


# ---------------------------------------------------------------------------
# DELETE /api/activity/{id}
# ---------------------------------------------------------------------------

class TestDeleteActivity:

    def test_delete_activity(self, client):
        entry = make_activity(client)
        resp = client.delete(f"/api/activity/{entry['id']}")
        assert resp.status_code == 204
        resp = client.get(f"/api/activity/{entry['id']}")
        assert resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete(f"/api/activity/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reference integrity — FK SET NULL on parent deletion
# ---------------------------------------------------------------------------

class TestActivityReferenceIntegrity:

    def test_task_deletion_nullifies_activity_reference(self, client):
        """Deleting a task sets activity_log.task_id to NULL, not cascading."""
        task = make_task(client)
        entry = make_activity(client, task_id=task["id"])

        client.delete(f"/api/tasks/{task['id']}")

        resp = client.get(f"/api/activity/{entry['id']}")
        assert resp.status_code == 200
        assert resp.json()["task_id"] is None

    def test_routine_deletion_nullifies_activity_reference(self, client):
        """Deleting a routine sets activity_log.routine_id to NULL."""
        domain = make_domain(client)
        routine = make_routine(client, domain["id"])
        entry = make_activity(
            client, routine_id=routine["id"], action_type="completed",
        )

        client.delete(f"/api/routines/{routine['id']}")

        resp = client.get(f"/api/activity/{entry['id']}")
        assert resp.status_code == 200
        assert resp.json()["routine_id"] is None

    def test_checkin_deletion_nullifies_activity_reference(self, client):
        """Deleting a check-in sets activity_log.checkin_id to NULL."""
        checkin = make_checkin(client)
        entry = make_activity(
            client, checkin_id=checkin["id"], action_type="checked_in",
        )

        client.delete(f"/api/checkins/{checkin['id']}")

        resp = client.get(f"/api/activity/{entry['id']}")
        assert resp.status_code == 200
        assert resp.json()["checkin_id"] is None
