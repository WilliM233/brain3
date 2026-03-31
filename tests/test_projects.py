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

"""Tests for Project CRUD endpoints."""

from datetime import date, timedelta

from tests.conftest import FAKE_UUID, make_domain, make_goal, make_project, make_task

# ---------------------------------------------------------------------------
# POST /api/projects
# ---------------------------------------------------------------------------

class TestCreateProject:

    def test_create_project(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        resp = client.post(
            "/api/projects",
            json={"goal_id": goal["id"], "title": "Build API"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Build API"
        assert body["goal_id"] == goal["id"]
        assert body["status"] == "not_started"
        assert body["progress_pct"] == 0

    def test_create_project_with_optional_fields(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        resp = client.post(
            "/api/projects",
            json={
                "goal_id": goal["id"],
                "title": "Launch MVP",
                "description": "Ship it",
                "status": "active",
                "deadline": "2026-06-01",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["description"] == "Ship it"
        assert body["status"] == "active"
        assert body["deadline"] == "2026-06-01"

    def test_create_project_missing_title(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        resp = client.post("/api/projects", json={"goal_id": goal["id"]})
        assert resp.status_code == 422

    def test_create_project_title_too_long(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        resp = client.post(
            "/api/projects",
            json={"goal_id": goal["id"], "title": "x" * 201},
        )
        assert resp.status_code == 422

    def test_create_project_invalid_status(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        resp = client.post(
            "/api/projects",
            json={"goal_id": goal["id"], "title": "Bad", "status": "INVALID"},
        )
        assert resp.status_code == 422

    def test_create_project_invalid_goal(self, client):
        resp = client.post(
            "/api/projects",
            json={"goal_id": FAKE_UUID, "title": "Orphan"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/projects
# ---------------------------------------------------------------------------

class TestListProjects:

    def test_list_projects_empty(self, client):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_projects(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        make_project(client, goal["id"], title="A")
        make_project(client, goal["id"], title="B")
        resp = client.get("/api/projects")
        assert len(resp.json()) == 2

    def test_filter_by_goal_id(self, client):
        domain = make_domain(client)
        g1 = make_goal(client, domain["id"], title="G1")
        g2 = make_goal(client, domain["id"], title="G2")
        make_project(client, g1["id"], title="P1")
        make_project(client, g2["id"], title="P2")

        resp = client.get(f"/api/projects?goal_id={g1['id']}")
        projects = resp.json()
        assert len(projects) == 1
        assert projects[0]["title"] == "P1"

    def test_filter_by_status(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        make_project(client, goal["id"], title="Active", status="active")
        make_project(client, goal["id"], title="Blocked", status="blocked")

        resp = client.get("/api/projects?status=blocked")
        projects = resp.json()
        assert len(projects) == 1
        assert projects[0]["title"] == "Blocked"

    def test_filter_has_deadline(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        make_project(client, goal["id"], title="With deadline", deadline="2026-12-31")
        make_project(client, goal["id"], title="No deadline")

        resp = client.get("/api/projects?has_deadline=true")
        projects = resp.json()
        assert len(projects) == 1
        assert projects[0]["title"] == "With deadline"

    def test_filter_overdue(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        make_project(client, goal["id"], title="Overdue", deadline=yesterday, status="active")
        make_project(client, goal["id"], title="Future", deadline=tomorrow, status="active")
        make_project(client, goal["id"], title="Done", deadline=yesterday, status="completed")

        resp = client.get("/api/projects?overdue=true")
        projects = resp.json()
        assert len(projects) == 1
        assert projects[0]["title"] == "Overdue"


# ---------------------------------------------------------------------------
# GET /api/projects/{id}
# ---------------------------------------------------------------------------

class TestGetProject:

    def test_get_project_detail(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        resp = client.get(f"/api/projects/{project['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == project["title"]
        assert "tasks" in body
        assert body["tasks"] == []

    def test_get_project_with_tasks(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        make_task(client, project_id=project["id"], title="T1")
        make_task(client, project_id=project["id"], title="T2")
        resp = client.get(f"/api/projects/{project['id']}")
        assert len(resp.json()["tasks"]) == 2

    def test_get_project_not_found(self, client):
        resp = client.get(f"/api/projects/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/projects/{id}
# ---------------------------------------------------------------------------

class TestUpdateProject:

    def test_patch_project(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"], title="Old")
        resp = client.patch(
            f"/api/projects/{project['id']}", json={"title": "New"}
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    def test_patch_project_partial(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"], title="Keep", status="active")
        resp = client.patch(
            f"/api/projects/{project['id']}", json={"status": "blocked"}
        )
        body = resp.json()
        assert body["title"] == "Keep"
        assert body["status"] == "blocked"

    def test_patch_project_invalid_status(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        resp = client.patch(
            f"/api/projects/{project['id']}", json={"status": "INVALID"},
        )
        assert resp.status_code == 422

    def test_patch_project_reparent_to_different_goal(self, client):
        """Move a project from one goal to another via PATCH."""
        domain = make_domain(client)
        goal_a = make_goal(client, domain["id"], title="Goal A")
        goal_b = make_goal(client, domain["id"], title="Goal B")
        project = make_project(client, goal_a["id"])

        resp = client.patch(
            f"/api/projects/{project['id']}", json={"goal_id": goal_b["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["goal_id"] == goal_b["id"]

        # Verify it shows under goal B's detail
        detail = client.get(f"/api/goals/{goal_b['id']}").json()
        project_ids = [p["id"] for p in detail["projects"]]
        assert project["id"] in project_ids

    def test_patch_project_not_found(self, client):
        resp = client.patch(f"/api/projects/{FAKE_UUID}", json={"title": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/projects/{id}
# ---------------------------------------------------------------------------

class TestDeleteProject:

    def test_delete_project(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        resp = client.delete(f"/api/projects/{project['id']}")
        assert resp.status_code == 204

        resp = client.get(f"/api/projects/{project['id']}")
        assert resp.status_code == 404

    def test_delete_project_cascades_tasks(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        task = make_task(client, project_id=project["id"])

        client.delete(f"/api/projects/{project['id']}")

        resp = client.get(f"/api/tasks/{task['id']}")
        assert resp.status_code == 404

    def test_delete_project_not_found(self, client):
        resp = client.delete(f"/api/projects/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# progress_pct dynamic computation (#69)
# ---------------------------------------------------------------------------

class TestProgressPct:

    def test_progress_zero_tasks(self, client):
        """Project with no tasks returns 0%."""
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        resp = client.get(f"/api/projects/{project['id']}")
        assert resp.json()["progress_pct"] == 0

    def test_progress_half_completed(self, client):
        """Project with 1/2 completed tasks returns 50%."""
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        make_task(client, project_id=project["id"], title="Done", status="completed")
        make_task(client, project_id=project["id"], title="Pending")
        resp = client.get(f"/api/projects/{project['id']}")
        assert resp.json()["progress_pct"] == 50

    def test_progress_all_completed(self, client):
        """Project with 2/2 completed tasks returns 100%."""
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        make_task(client, project_id=project["id"], title="A", status="completed")
        make_task(client, project_id=project["id"], title="B", status="completed")
        resp = client.get(f"/api/projects/{project['id']}")
        assert resp.json()["progress_pct"] == 100

    def test_progress_all_pending(self, client):
        """Project with all pending tasks returns 0%."""
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        make_task(client, project_id=project["id"], title="A")
        make_task(client, project_id=project["id"], title="B")
        resp = client.get(f"/api/projects/{project['id']}")
        assert resp.json()["progress_pct"] == 0

    def test_progress_on_list_endpoint(self, client):
        """list_projects also returns computed progress_pct."""
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        make_task(client, project_id=project["id"], title="Done", status="completed")
        make_task(client, project_id=project["id"], title="Pending")
        resp = client.get("/api/projects")
        projects = resp.json()
        assert len(projects) == 1
        assert projects[0]["progress_pct"] == 50
