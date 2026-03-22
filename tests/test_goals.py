"""Tests for Goal CRUD endpoints."""

from tests.conftest import FAKE_UUID, make_domain, make_goal

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

    def test_delete_goal_not_found(self, client):
        resp = client.delete(f"/api/goals/{FAKE_UUID}")
        assert resp.status_code == 404
