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

"""Tests for Goal CRUD endpoints."""

from tests.conftest import FAKE_UUID, make_domain, make_goal, make_project, make_task

# ---------------------------------------------------------------------------
# POST /api/goals
# ---------------------------------------------------------------------------

class TestCreateGoal:

    def test_create_goal(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/goals",
            json={"domain_id": domain["id"], "title": "Run daily"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Run daily"
        assert body["domain_id"] == domain["id"]
        assert body["status"] == "active"

    def test_create_goal_with_optional_fields(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/goals",
            json={
                "domain_id": domain["id"],
                "title": "Save money",
                "description": "Emergency fund",
                "status": "paused",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["description"] == "Emergency fund"
        assert body["status"] == "paused"

    def test_create_goal_missing_title(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/goals", json={"domain_id": domain["id"]}
        )
        assert resp.status_code == 422

    def test_create_goal_title_too_long(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/goals",
            json={"domain_id": domain["id"], "title": "x" * 201},
        )
        assert resp.status_code == 422

    def test_create_goal_invalid_status(self, client):
        domain = make_domain(client)
        resp = client.post(
            "/api/goals",
            json={"domain_id": domain["id"], "title": "Bad", "status": "INVALID"},
        )
        assert resp.status_code == 422

    def test_create_goal_invalid_domain(self, client):
        resp = client.post(
            "/api/goals",
            json={"domain_id": FAKE_UUID, "title": "Orphan goal"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/goals
# ---------------------------------------------------------------------------

class TestListGoals:

    def test_list_goals_empty(self, client):
        resp = client.get("/api/goals")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_goals(self, client):
        domain = make_domain(client)
        make_goal(client, domain["id"], title="A")
        make_goal(client, domain["id"], title="B")
        resp = client.get("/api/goals")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_domain_id(self, client):
        d1 = make_domain(client, name="D1")
        d2 = make_domain(client, name="D2")
        make_goal(client, d1["id"], title="G1")
        make_goal(client, d2["id"], title="G2")

        resp = client.get(f"/api/goals?domain_id={d1['id']}")
        assert resp.status_code == 200
        goals = resp.json()
        assert len(goals) == 1
        assert goals[0]["title"] == "G1"

    def test_filter_by_status(self, client):
        domain = make_domain(client)
        make_goal(client, domain["id"], title="Active", status="active")
        make_goal(client, domain["id"], title="Paused", status="paused")

        resp = client.get("/api/goals?status=paused")
        assert resp.status_code == 200
        goals = resp.json()
        assert len(goals) == 1
        assert goals[0]["title"] == "Paused"


# ---------------------------------------------------------------------------
# GET /api/goals/{id}
# ---------------------------------------------------------------------------

class TestGetGoal:

    def test_get_goal_detail(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        resp = client.get(f"/api/goals/{goal['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == goal["title"]
        assert "projects" in body
        assert body["projects"] == []

    def test_get_goal_not_found(self, client):
        resp = client.get(f"/api/goals/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/goals/{id}
# ---------------------------------------------------------------------------

class TestUpdateGoal:

    def test_patch_goal(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"], title="Old")
        resp = client.patch(
            f"/api/goals/{goal['id']}", json={"title": "New"}
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    def test_patch_goal_partial(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"], title="Keep", status="active")
        resp = client.patch(
            f"/api/goals/{goal['id']}", json={"status": "paused"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Keep"
        assert body["status"] == "paused"

    def test_patch_goal_invalid_status(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        resp = client.patch(
            f"/api/goals/{goal['id']}", json={"status": "INVALID"},
        )
        assert resp.status_code == 422

    def test_patch_goal_reparent_to_different_domain(self, client):
        """Move a goal from one domain to another via PATCH."""
        domain_a = make_domain(client, name="Domain A")
        domain_b = make_domain(client, name="Domain B")
        goal = make_goal(client, domain_a["id"])

        resp = client.patch(
            f"/api/goals/{goal['id']}", json={"domain_id": domain_b["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["domain_id"] == domain_b["id"]

        # Verify it shows under domain B's detail
        detail = client.get(f"/api/domains/{domain_b['id']}").json()
        goal_ids = [g["id"] for g in detail["goals"]]
        assert goal["id"] in goal_ids

    def test_patch_goal_not_found(self, client):
        resp = client.patch(f"/api/goals/{FAKE_UUID}", json={"title": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/goals/{id}
# ---------------------------------------------------------------------------

class TestDeleteGoal:

    def test_delete_goal(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        resp = client.delete(f"/api/goals/{goal['id']}")
        assert resp.status_code == 204

        resp = client.get(f"/api/goals/{goal['id']}")
        assert resp.status_code == 404

    def test_delete_goal_cascades_projects_and_tasks(self, client):
        """Delete a goal and verify child projects and tasks are removed."""
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])
        task = make_task(client, project_id=project["id"])

        client.delete(f"/api/goals/{goal['id']}")

        assert client.get(f"/api/projects/{project['id']}").status_code == 404
        assert client.get(f"/api/tasks/{task['id']}").status_code == 404

    def test_delete_goal_not_found(self, client):
        resp = client.delete(f"/api/goals/{FAKE_UUID}")
        assert resp.status_code == 404
