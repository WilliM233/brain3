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

"""Tests for Protocols — CRUD, JSONB steps, tagging, filters, version logic."""

from tests.conftest import FAKE_UUID, make_tag

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_STEPS = [
    {
        "order": 1, "title": "Check context",
        "instruction": "Read the brief and issue.",
        "is_optional": False,
    },
    {
        "order": 2, "title": "Set up branch",
        "instruction": "Create feature branch from develop.",
        "is_optional": False,
    },
    {
        "order": 3, "title": "Run smoke test",
        "instruction": "Verify dev environment.",
        "is_optional": True,
    },
]


def make_artifact(client, **overrides) -> dict:
    """Create an artifact via the API and return the response JSON."""
    data = {
        "title": "Test Artifact",
        "artifact_type": "document",
        "content": "Hello, world!",
        **overrides,
    }
    resp = client.post("/api/artifacts", json=data)
    assert resp.status_code == 201
    return resp.json()


def make_protocol(client, **overrides) -> dict:
    """Create a protocol via the API and return the response JSON."""
    data = {"name": "test-protocol", **overrides}
    resp = client.post("/api/protocols", json=data)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/protocols — Create
# ---------------------------------------------------------------------------

class TestCreateProtocol:

    def test_create_minimal(self, client):
        resp = client.post("/api/protocols", json={"name": "session-startup"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "session-startup"
        assert body["description"] is None
        assert body["steps"] is None
        assert body["artifact_id"] is None
        assert body["is_seedable"] is True
        assert body["version"] == 1
        assert body["tags"] == []

    def test_create_with_steps(self, client):
        resp = client.post("/api/protocols", json={
            "name": "agent-activation",
            "steps": SAMPLE_STEPS,
        })
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["steps"]) == 3
        assert body["steps"][0]["title"] == "Check context"
        assert body["steps"][2]["is_optional"] is True

    def test_create_with_all_fields(self, client):
        artifact = make_artifact(client)
        tag = make_tag(client, name="ops")
        resp = client.post("/api/protocols", json={
            "name": "full-protocol",
            "description": "A fully specified protocol.",
            "steps": SAMPLE_STEPS[:1],
            "artifact_id": artifact["id"],
            "is_seedable": False,
            "tag_ids": [tag["id"]],
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["description"] == "A fully specified protocol."
        assert body["artifact_id"] == artifact["id"]
        assert body["is_seedable"] is False
        assert len(body["tags"]) == 1
        assert body["tags"][0]["name"] == "ops"

    def test_create_duplicate_name_409(self, client):
        make_protocol(client, name="unique-name")
        resp = client.post("/api/protocols", json={"name": "unique-name"})
        assert resp.status_code == 409

    def test_create_with_invalid_artifact_id(self, client):
        resp = client.post("/api/protocols", json={
            "name": "bad-artifact",
            "artifact_id": FAKE_UUID,
        })
        assert resp.status_code == 400

    def test_create_with_invalid_tag_id(self, client):
        resp = client.post("/api/protocols", json={
            "name": "bad-tag",
            "tag_ids": [FAKE_UUID],
        })
        assert resp.status_code == 400

    def test_create_steps_validation_order_min(self, client):
        resp = client.post("/api/protocols", json={
            "name": "bad-steps",
            "steps": [{"order": 0, "title": "X", "instruction": "Y"}],
        })
        assert resp.status_code == 422

    def test_create_steps_validation_missing_fields(self, client):
        resp = client.post("/api/protocols", json={
            "name": "bad-steps-2",
            "steps": [{"order": 1}],
        })
        assert resp.status_code == 422

    def test_name_preserves_casing(self, client):
        resp = client.post("/api/protocols", json={"name": "Session-Startup"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "Session-Startup"


# ---------------------------------------------------------------------------
# GET /api/protocols — List
# ---------------------------------------------------------------------------

class TestListProtocols:

    def test_list_empty(self, client):
        resp = client.get("/api/protocols")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_all(self, client):
        make_protocol(client, name="alpha")
        make_protocol(client, name="beta")
        resp = client.get("/api/protocols")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_filter_search(self, client):
        make_protocol(client, name="session-startup")
        make_protocol(client, name="bug-discovery")
        resp = client.get("/api/protocols", params={"search": "session"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "session-startup"

    def test_list_filter_search_case_insensitive(self, client):
        make_protocol(client, name="Session-Startup")
        resp = client.get("/api/protocols", params={"search": "session"})
        assert len(resp.json()) == 1

    def test_list_filter_is_seedable(self, client):
        make_protocol(client, name="seedable", is_seedable=True)
        make_protocol(client, name="not-seedable", is_seedable=False)
        resp = client.get("/api/protocols", params={"is_seedable": True})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "seedable"

    def test_list_filter_has_artifact_true(self, client):
        artifact = make_artifact(client)
        make_protocol(client, name="with-artifact", artifact_id=artifact["id"])
        make_protocol(client, name="without-artifact")
        resp = client.get("/api/protocols", params={"has_artifact": True})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "with-artifact"

    def test_list_filter_has_artifact_false(self, client):
        artifact = make_artifact(client)
        make_protocol(client, name="with-artifact", artifact_id=artifact["id"])
        make_protocol(client, name="without-artifact")
        resp = client.get("/api/protocols", params={"has_artifact": False})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "without-artifact"

    def test_list_filter_tag(self, client):
        tag = make_tag(client, name="ops")
        p = make_protocol(client, name="tagged-protocol")
        client.post(f"/api/protocols/{p['id']}/tags/{tag['id']}")
        make_protocol(client, name="untagged")
        resp = client.get("/api/protocols", params={"tag": "ops"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "tagged-protocol"

    def test_list_filter_tag_and_logic(self, client):
        tag1 = make_tag(client, name="ops")
        tag2 = make_tag(client, name="startup")
        p = make_protocol(client, name="both-tags")
        client.post(f"/api/protocols/{p['id']}/tags/{tag1['id']}")
        client.post(f"/api/protocols/{p['id']}/tags/{tag2['id']}")
        p2 = make_protocol(client, name="one-tag")
        client.post(f"/api/protocols/{p2['id']}/tags/{tag1['id']}")
        resp = client.get("/api/protocols", params={"tag": "ops,startup"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "both-tags"


# ---------------------------------------------------------------------------
# GET /api/protocols/{id} — Detail
# ---------------------------------------------------------------------------

class TestGetProtocol:

    def test_get_protocol(self, client):
        p = make_protocol(client, name="get-me", steps=SAMPLE_STEPS)
        resp = client.get(f"/api/protocols/{p['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "get-me"
        assert len(body["steps"]) == 3
        assert "artifact" in body  # detail field

    def test_get_protocol_resolves_artifact(self, client):
        artifact = make_artifact(client, title="Protocol Docs")
        p = make_protocol(client, name="with-art", artifact_id=artifact["id"])
        resp = client.get(f"/api/protocols/{p['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["artifact"] is not None
        assert body["artifact"]["title"] == "Protocol Docs"

    def test_get_protocol_not_found(self, client):
        resp = client.get(f"/api/protocols/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/protocols/{id} — Update
# ---------------------------------------------------------------------------

class TestUpdateProtocol:

    def test_update_name(self, client):
        p = make_protocol(client, name="old-name")
        resp = client.patch(f"/api/protocols/{p['id']}", json={"name": "new-name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "new-name"
        # Name-only change should NOT bump version
        assert resp.json()["version"] == 1

    def test_update_steps_bumps_version(self, client):
        p = make_protocol(client, name="versioned", steps=SAMPLE_STEPS)
        new_steps = [{"order": 1, "title": "New step", "instruction": "Do the thing."}]
        resp = client.patch(f"/api/protocols/{p['id']}", json={"steps": new_steps})
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == 2
        assert len(body["steps"]) == 1
        assert body["steps"][0]["title"] == "New step"

    def test_update_description_bumps_version(self, client):
        p = make_protocol(client, name="desc-version")
        resp = client.patch(f"/api/protocols/{p['id']}", json={"description": "Updated."})
        assert resp.status_code == 200
        assert resp.json()["version"] == 2

    def test_update_is_seedable_no_version_bump(self, client):
        p = make_protocol(client, name="seedable-change")
        resp = client.patch(f"/api/protocols/{p['id']}", json={"is_seedable": False})
        assert resp.status_code == 200
        assert resp.json()["is_seedable"] is False
        assert resp.json()["version"] == 1

    def test_update_duplicate_name_409(self, client):
        make_protocol(client, name="taken")
        p = make_protocol(client, name="available")
        resp = client.patch(f"/api/protocols/{p['id']}", json={"name": "taken"})
        assert resp.status_code == 409

    def test_update_same_name_no_conflict(self, client):
        p = make_protocol(client, name="keep-name")
        resp = client.patch(f"/api/protocols/{p['id']}", json={"name": "keep-name"})
        assert resp.status_code == 200

    def test_update_artifact_id(self, client):
        artifact = make_artifact(client)
        p = make_protocol(client, name="link-artifact")
        resp = client.patch(f"/api/protocols/{p['id']}", json={"artifact_id": artifact["id"]})
        assert resp.status_code == 200
        assert resp.json()["artifact_id"] == artifact["id"]
        assert resp.json()["version"] == 1  # metadata only

    def test_update_invalid_artifact_id(self, client):
        p = make_protocol(client, name="bad-art-update")
        resp = client.patch(f"/api/protocols/{p['id']}", json={"artifact_id": FAKE_UUID})
        assert resp.status_code == 400

    def test_update_not_found(self, client):
        resp = client.patch(f"/api/protocols/{FAKE_UUID}", json={"name": "x"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/protocols/{id}
# ---------------------------------------------------------------------------

class TestDeleteProtocol:

    def test_delete(self, client):
        p = make_protocol(client, name="delete-me")
        resp = client.delete(f"/api/protocols/{p['id']}")
        assert resp.status_code == 204
        assert client.get(f"/api/protocols/{p['id']}").status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete(f"/api/protocols/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Artifact FK — SET NULL on delete
# ---------------------------------------------------------------------------

class TestArtifactFK:

    def test_delete_artifact_sets_null(self, client):
        artifact = make_artifact(client)
        p = make_protocol(client, name="art-ref", artifact_id=artifact["id"])
        assert p["artifact_id"] == artifact["id"]

        client.delete(f"/api/artifacts/{artifact['id']}")
        resp = client.get(f"/api/protocols/{p['id']}")
        assert resp.status_code == 200
        assert resp.json()["artifact_id"] is None


# ---------------------------------------------------------------------------
# Protocol-Tag attachment
# ---------------------------------------------------------------------------

class TestProtocolTagging:

    def test_attach_tag(self, client):
        p = make_protocol(client, name="tag-test")
        tag = make_tag(client, name="agent")
        resp = client.post(f"/api/protocols/{p['id']}/tags/{tag['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "agent"

    def test_attach_tag_idempotent(self, client):
        p = make_protocol(client, name="idem-test")
        tag = make_tag(client, name="agent")
        client.post(f"/api/protocols/{p['id']}/tags/{tag['id']}")
        resp = client.post(f"/api/protocols/{p['id']}/tags/{tag['id']}")
        assert resp.status_code == 200
        # Only one tag attached
        tags_resp = client.get(f"/api/protocols/{p['id']}/tags")
        assert len(tags_resp.json()) == 1

    def test_list_tags_on_protocol(self, client):
        p = make_protocol(client, name="list-tags")
        tag1 = make_tag(client, name="alpha")
        tag2 = make_tag(client, name="beta")
        client.post(f"/api/protocols/{p['id']}/tags/{tag1['id']}")
        client.post(f"/api/protocols/{p['id']}/tags/{tag2['id']}")
        resp = client.get(f"/api/protocols/{p['id']}/tags")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_detach_tag(self, client):
        p = make_protocol(client, name="detach-test")
        tag = make_tag(client, name="remove-me")
        client.post(f"/api/protocols/{p['id']}/tags/{tag['id']}")
        resp = client.delete(f"/api/protocols/{p['id']}/tags/{tag['id']}")
        assert resp.status_code == 204
        tags_resp = client.get(f"/api/protocols/{p['id']}/tags")
        assert len(tags_resp.json()) == 0

    def test_detach_tag_not_attached(self, client):
        p = make_protocol(client, name="not-attached")
        tag = make_tag(client, name="loose")
        resp = client.delete(f"/api/protocols/{p['id']}/tags/{tag['id']}")
        assert resp.status_code == 404

    def test_attach_tag_protocol_not_found(self, client):
        tag = make_tag(client, name="orphan-tag")
        resp = client.post(f"/api/protocols/{FAKE_UUID}/tags/{tag['id']}")
        assert resp.status_code == 404

    def test_attach_tag_tag_not_found(self, client):
        p = make_protocol(client, name="no-tag")
        resp = client.post(f"/api/protocols/{p['id']}/tags/{FAKE_UUID}")
        assert resp.status_code == 404

    def test_list_tags_protocol_not_found(self, client):
        resp = client.get(f"/api/protocols/{FAKE_UUID}/tags")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reverse lookup — /api/tags/{tag_id}/protocols
# ---------------------------------------------------------------------------

class TestTagReverseProtocols:

    def test_reverse_lookup(self, client):
        tag = make_tag(client, name="reverse-test")
        p = make_protocol(client, name="reverse-p")
        client.post(f"/api/protocols/{p['id']}/tags/{tag['id']}")
        resp = client.get(f"/api/tags/{tag['id']}/protocols")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "reverse-p"

    def test_reverse_lookup_empty(self, client):
        tag = make_tag(client, name="empty-reverse")
        resp = client.get(f"/api/tags/{tag['id']}/protocols")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_reverse_lookup_tag_not_found(self, client):
        resp = client.get(f"/api/tags/{FAKE_UUID}/protocols")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# tag_ids on create
# ---------------------------------------------------------------------------

class TestCreateWithTagIds:

    def test_tag_ids_on_create(self, client):
        tag1 = make_tag(client, name="t1")
        tag2 = make_tag(client, name="t2")
        resp = client.post("/api/protocols", json={
            "name": "tagged-create",
            "tag_ids": [tag1["id"], tag2["id"]],
        })
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["tags"]) == 2
        tag_names = {t["name"] for t in body["tags"]}
        assert tag_names == {"t1", "t2"}
