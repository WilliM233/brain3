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

"""Tests for Task CRUD endpoints."""

from datetime import date, timedelta

from tests.conftest import FAKE_UUID, make_domain, make_goal, make_project, make_task

# ---------------------------------------------------------------------------
# POST /api/tasks
# ---------------------------------------------------------------------------

class TestCreateTask:

    def test_create_standalone_task(self, client):
        resp = client.post("/api/tasks", json={"title": "Buy groceries"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Buy groceries"
        assert body["project_id"] is None
        assert body["status"] == "pending"

    def test_create_task_with_project(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        resp = client.post(
            "/api/tasks",
            json={"project_id": project["id"], "title": "Subtask"},
        )
        assert resp.status_code == 201
        assert resp.json()["project_id"] == project["id"]

    def test_create_task_with_adhd_metadata(self, client):
        resp = client.post(
            "/api/tasks",
            json={
                "title": "Deep focus work",
                "cognitive_type": "focus_work",
                "energy_cost": 4,
                "activation_friction": 3,
                "context_required": "at_computer",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["cognitive_type"] == "focus_work"
        assert body["energy_cost"] == 4
        assert body["activation_friction"] == 3
        assert body["context_required"] == "at_computer"

    def test_create_task_missing_title(self, client):
        resp = client.post("/api/tasks", json={})
        assert resp.status_code == 422

    def test_create_task_invalid_project(self, client):
        resp = client.post(
            "/api/tasks",
            json={"project_id": FAKE_UUID, "title": "Orphan"},
        )
        assert resp.status_code == 400

    def test_create_task_energy_cost_out_of_range(self, client):
        resp = client.post(
            "/api/tasks", json={"title": "Bad", "energy_cost": 6}
        )
        assert resp.status_code == 422

    def test_create_task_energy_cost_zero(self, client):
        resp = client.post(
            "/api/tasks", json={"title": "Bad", "energy_cost": 0}
        )
        assert resp.status_code == 422

    def test_create_task_friction_out_of_range(self, client):
        resp = client.post(
            "/api/tasks", json={"title": "Bad", "activation_friction": 10}
        )
        assert resp.status_code == 422

    def test_create_task_title_too_long(self, client):
        resp = client.post(
            "/api/tasks", json={"title": "x" * 201},
        )
        assert resp.status_code == 422

    def test_create_task_context_too_long(self, client):
        resp = client.post(
            "/api/tasks", json={"title": "Valid", "context_required": "x" * 101},
        )
        assert resp.status_code == 422

    def test_create_task_invalid_status(self, client):
        resp = client.post(
            "/api/tasks", json={"title": "Bad", "status": "INVALID"},
        )
        assert resp.status_code == 422

    def test_create_task_invalid_cognitive_type(self, client):
        resp = client.post(
            "/api/tasks", json={"title": "Bad", "cognitive_type": "INVALID"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/tasks — composable filters
# ---------------------------------------------------------------------------

class TestListTasks:

    def test_list_tasks_empty(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_tasks(self, client):
        make_task(client, title="A")
        make_task(client, title="B")
        resp = client.get("/api/tasks")
        assert len(resp.json()) == 2

    def test_filter_by_project_id(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        make_task(client, project_id=project["id"], title="In project")
        make_task(client, title="Standalone")

        resp = client.get(f"/api/tasks?project_id={project['id']}")
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "In project"

    def test_filter_standalone(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        make_task(client, project_id=project["id"], title="In project")
        make_task(client, title="Standalone")

        resp = client.get("/api/tasks?standalone=true")
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Standalone"

    def test_filter_by_status(self, client):
        make_task(client, title="Pending", status="pending")
        make_task(client, title="Active", status="active")

        resp = client.get("/api/tasks?status=active")
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Active"

    def test_filter_by_cognitive_type(self, client):
        make_task(client, title="Errand", cognitive_type="errand")
        make_task(client, title="Focus", cognitive_type="focus_work")

        resp = client.get("/api/tasks?cognitive_type=errand")
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Errand"

    def test_filter_energy_cost_range(self, client):
        make_task(client, title="Low", energy_cost=1)
        make_task(client, title="Medium", energy_cost=3)
        make_task(client, title="High", energy_cost=5)

        resp = client.get("/api/tasks?energy_cost_min=1&energy_cost_max=2")
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Low"

    def test_filter_friction_range(self, client):
        make_task(client, title="Easy", activation_friction=1)
        make_task(client, title="Hard", activation_friction=4)

        resp = client.get("/api/tasks?friction_max=2")
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Easy"

    def test_filter_by_context(self, client):
        make_task(client, title="Home", context_required="at_home")
        make_task(client, title="Store", context_required="at_store")

        resp = client.get("/api/tasks?context_required=at_home")
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Home"

    def test_filter_due_before(self, client):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        next_week = (date.today() + timedelta(days=7)).isoformat()
        make_task(client, title="Soon", due_date=tomorrow)
        make_task(client, title="Later", due_date=next_week)

        resp = client.get(f"/api/tasks?due_before={tomorrow}")
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Soon"

    def test_filter_due_after(self, client):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        next_week = (date.today() + timedelta(days=7)).isoformat()
        make_task(client, title="Soon", due_date=tomorrow)
        make_task(client, title="Later", due_date=next_week)

        resp = client.get(f"/api/tasks?due_after={next_week}")
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Later"

    def test_filter_overdue(self, client):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        make_task(client, title="Overdue", due_date=yesterday, status="pending")
        make_task(client, title="Future", due_date=tomorrow, status="pending")
        make_task(client, title="Done", due_date=yesterday, status="completed")

        resp = client.get("/api/tasks?overdue=true")
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Overdue"

    def test_filter_overdue_excludes_skipped(self, client):
        """Overdue filter excludes completed and skipped, but includes deferred."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        make_task(client, title="Skipped", due_date=yesterday, status="skipped")
        make_task(client, title="Deferred", due_date=yesterday, status="deferred")

        resp = client.get("/api/tasks?overdue=true")
        tasks = resp.json()
        titles = [t["title"] for t in tasks]
        assert "Skipped" not in titles
        assert "Deferred" in titles

    def test_composable_filters(self, client):
        make_task(
            client, title="Match",
            energy_cost=2, context_required="at_home", status="pending",
        )
        make_task(
            client, title="Wrong energy",
            energy_cost=5, context_required="at_home", status="pending",
        )
        make_task(
            client, title="Wrong context",
            energy_cost=2, context_required="at_store", status="pending",
        )

        resp = client.get(
            "/api/tasks?energy_cost_max=2&context_required=at_home&status=pending"
        )
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Match"


# ---------------------------------------------------------------------------
# GET /api/tasks/{id}
# ---------------------------------------------------------------------------

class TestGetTask:

    def test_get_task_detail(self, client):
        task = make_task(client)
        resp = client.get(f"/api/tasks/{task['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == task["title"]
        assert "tags" in body
        assert body["tags"] == []

    def test_get_task_not_found(self, client):
        resp = client.get(f"/api/tasks/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/tasks/{id}
# ---------------------------------------------------------------------------

class TestUpdateTask:

    def test_patch_task(self, client):
        task = make_task(client, title="Old")
        resp = client.patch(
            f"/api/tasks/{task['id']}", json={"title": "New"}
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    def test_patch_task_partial(self, client):
        task = make_task(client, title="Keep", energy_cost=3)
        resp = client.patch(
            f"/api/tasks/{task['id']}", json={"energy_cost": 1}
        )
        body = resp.json()
        assert body["title"] == "Keep"
        assert body["energy_cost"] == 1

    def test_patch_task_reparent_to_different_project(self, client):
        """Move a task from one project to another via PATCH."""
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project_a = make_project(client, goal["id"], title="Project A")
        project_b = make_project(client, goal["id"], title="Project B")
        task = make_task(client, project_id=project_a["id"])

        resp = client.patch(
            f"/api/tasks/{task['id']}", json={"project_id": project_b["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["project_id"] == project_b["id"]

    def test_patch_task_make_standalone(self, client):
        """Detach a task from its project to make it standalone."""
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        task = make_task(client, project_id=project["id"])

        resp = client.patch(
            f"/api/tasks/{task['id']}", json={"project_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["project_id"] is None

    def test_patch_task_not_found(self, client):
        resp = client.patch(f"/api/tasks/{FAKE_UUID}", json={"title": "X"})
        assert resp.status_code == 404

    def test_patch_task_invalid_energy(self, client):
        task = make_task(client)
        resp = client.patch(
            f"/api/tasks/{task['id']}", json={"energy_cost": 7}
        )
        assert resp.status_code == 422

    def test_patch_task_invalid_status(self, client):
        task = make_task(client)
        resp = client.patch(
            f"/api/tasks/{task['id']}", json={"status": "INVALID"},
        )
        assert resp.status_code == 422

    def test_patch_task_invalid_cognitive_type(self, client):
        task = make_task(client)
        resp = client.patch(
            f"/api/tasks/{task['id']}", json={"cognitive_type": "INVALID"},
        )
        assert resp.status_code == 422

    def test_patch_task_completed_at_auto_set(self, client):
        task = make_task(client)
        assert task["completed_at"] is None
        resp = client.patch(
            f"/api/tasks/{task['id']}", json={"status": "completed"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["completed_at"] is not None

    def test_patch_task_completed_at_cleared_on_revert(self, client):
        task = make_task(client)
        client.patch(f"/api/tasks/{task['id']}", json={"status": "completed"})
        resp = client.patch(
            f"/api/tasks/{task['id']}", json={"status": "active"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "active"
        assert body["completed_at"] is None

    def test_patch_task_completed_at_preserved(self, client):
        task = make_task(client)
        completed = client.patch(
            f"/api/tasks/{task['id']}", json={"status": "completed"},
        ).json()
        resp = client.patch(
            f"/api/tasks/{task['id']}", json={"title": "Updated"},
        )
        body = resp.json()
        assert body["title"] == "Updated"
        assert body["completed_at"] == completed["completed_at"]


# ---------------------------------------------------------------------------
# DELETE /api/tasks/{id}
# ---------------------------------------------------------------------------

class TestDeleteTask:

    def test_delete_task(self, client):
        task = make_task(client)
        resp = client.delete(f"/api/tasks/{task['id']}")
        assert resp.status_code == 204

        resp = client.get(f"/api/tasks/{task['id']}")
        assert resp.status_code == 404

    def test_delete_task_not_found(self, client):
        resp = client.delete(f"/api/tasks/{FAKE_UUID}")
        assert resp.status_code == 404
