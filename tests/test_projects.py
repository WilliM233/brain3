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
