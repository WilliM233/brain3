"""Tests for Domain CRUD endpoints."""

from tests.conftest import FAKE_UUID, make_domain, make_goal

# ---------------------------------------------------------------------------
# POST /api/domains
# ---------------------------------------------------------------------------

class TestCreateDomain:

    def test_create_domain(self, client):
        resp = client.post("/api/domains", json={"name": "Health"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Health"
        assert body["id"] is not None
        assert body["created_at"] is not None

    def test_create_domain_with_optional_fields(self, client):
        resp = client.post(
            "/api/domains",
            json={
                "name": "Finance",
                "description": "Money stuff",
                "color": "#00FF00",
                "sort_order": 5,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["description"] == "Money stuff"
        assert body["color"] == "#00FF00"
        assert body["sort_order"] == 5

    def test_create_domain_missing_name(self, client):
        resp = client.post("/api/domains", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/domains
# ---------------------------------------------------------------------------

class TestListDomains:

    def test_list_domains_empty(self, client):
        resp = client.get("/api/domains")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_domains(self, client):
        make_domain(client, name="A")
        make_domain(client, name="B")
        resp = client.get("/api/domains")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# GET /api/domains/{id}
# ---------------------------------------------------------------------------

class TestGetDomain:

    def test_get_domain_detail(self, client):
        domain = make_domain(client)
        resp = client.get(f"/api/domains/{domain['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == domain["name"]
        assert "goals" in body
        assert body["goals"] == []

    def test_get_domain_with_goals(self, client):
        domain = make_domain(client)
        make_goal(client, domain["id"], title="Goal 1")
        make_goal(client, domain["id"], title="Goal 2")
        resp = client.get(f"/api/domains/{domain['id']}")
        assert resp.status_code == 200
        assert len(resp.json()["goals"]) == 2

    def test_get_domain_not_found(self, client):
        resp = client.get(f"/api/domains/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/domains/{id}
# ---------------------------------------------------------------------------

class TestUpdateDomain:

    def test_patch_domain(self, client):
        domain = make_domain(client, name="Old")
        resp = client.patch(
            f"/api/domains/{domain['id']}", json={"name": "New"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_patch_domain_partial(self, client):
        domain = make_domain(client, name="Keep", color="#FF0000")
        resp = client.patch(
            f"/api/domains/{domain['id']}", json={"color": "#0000FF"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Keep"
        assert body["color"] == "#0000FF"

    def test_patch_domain_not_found(self, client):
        resp = client.patch(f"/api/domains/{FAKE_UUID}", json={"name": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/domains/{id}
# ---------------------------------------------------------------------------

class TestDeleteDomain:

    def test_delete_domain(self, client):
        domain = make_domain(client)
        resp = client.delete(f"/api/domains/{domain['id']}")
        assert resp.status_code == 204

        resp = client.get(f"/api/domains/{domain['id']}")
        assert resp.status_code == 404

    def test_delete_domain_cascades_goals(self, client):
        domain = make_domain(client)
        goal = make_goal(client, domain["id"])

        client.delete(f"/api/domains/{domain['id']}")

        resp = client.get(f"/api/goals/{goal['id']}")
        assert resp.status_code == 404

    def test_delete_domain_not_found(self, client):
        resp = client.delete(f"/api/domains/{FAKE_UUID}")
        assert resp.status_code == 404
