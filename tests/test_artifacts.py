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

"""Tests for Artifacts — CRUD, tagging, filters, parent relationships, version logic."""

from tests.conftest import FAKE_UUID, make_tag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# POST /api/artifacts — Create
# ---------------------------------------------------------------------------

class TestCreateArtifact:

    def test_create_minimal(self, client):
        resp = client.post("/api/artifacts", json={
            "title": "My Doc",
            "artifact_type": "document",
            "content": "Some content",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "My Doc"
        assert body["artifact_type"] == "document"
        assert body["version"] == 1
        assert body["is_seedable"] is False
        assert body["parent_id"] is None
        assert "content" not in body  # list-style response — no content

    def test_create_computes_content_size(self, client):
        content = "Hello, BRAIN!"
        artifact = make_artifact(client, content=content)
        assert artifact["content_size"] == len(content.encode("utf-8"))

    def test_create_content_size_utf8(self, client):
        content = "Héllo wörld 🧠"
        artifact = make_artifact(client, content=content)
        assert artifact["content_size"] == len(content.encode("utf-8"))

    def test_create_with_parent(self, client):
        parent = make_artifact(client, title="Part 1")
        child = make_artifact(client, title="Part 2", parent_id=parent["id"])
        assert child["parent_id"] == parent["id"]

    def test_create_with_invalid_parent(self, client):
        resp = client.post("/api/artifacts", json={
            "title": "Orphan",
            "artifact_type": "document",
            "content": "Content",
            "parent_id": FAKE_UUID,
        })
        assert resp.status_code == 400

    def test_create_with_tag_ids(self, client):
        tag1 = make_tag(client, name="claude-md")
        tag2 = make_tag(client, name="protocol")
        resp = client.post("/api/artifacts", json={
            "title": "Tagged Doc",
            "artifact_type": "document",
            "content": "Content",
            "tag_ids": [tag1["id"], tag2["id"]],
        })
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["tags"]) == 2
        tag_names = {t["name"] for t in body["tags"]}
        assert tag_names == {"claude-md", "protocol"}

    def test_create_with_invalid_tag_id(self, client):
        resp = client.post("/api/artifacts", json={
            "title": "Bad Tags",
            "artifact_type": "document",
            "content": "Content",
            "tag_ids": [FAKE_UUID],
        })
        assert resp.status_code == 400

    def test_create_invalid_artifact_type(self, client):
        resp = client.post("/api/artifacts", json={
            "title": "Bad Type",
            "artifact_type": "invalid_type",
            "content": "Content",
        })
        assert resp.status_code == 422

    def test_create_all_valid_types(self, client):
        for atype in ("document", "protocol", "brief", "prompt", "template", "journal", "spec"):
            resp = client.post("/api/artifacts", json={
                "title": f"Test {atype}",
                "artifact_type": atype,
                "content": "Content",
            })
            assert resp.status_code == 201, f"Failed for type: {atype}"

    def test_create_seedable(self, client):
        artifact = make_artifact(client, is_seedable=True)
        assert artifact["is_seedable"] is True

    def test_create_content_too_long(self, client):
        resp = client.post("/api/artifacts", json={
            "title": "Too Big",
            "artifact_type": "document",
            "content": "x" * 500_001,
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/artifacts — List (metadata only)
# ---------------------------------------------------------------------------

class TestListArtifacts:

    def test_list_returns_metadata_only(self, client):
        make_artifact(client, content="Secret content inside")
        resp = client.get("/api/artifacts")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert "content" not in body[0]
        assert "content_size" in body[0]

    def test_list_empty(self, client):
        resp = client.get("/api/artifacts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filter_by_artifact_type(self, client):
        make_artifact(client, artifact_type="document")
        make_artifact(client, title="Brief", artifact_type="brief")
        resp = client.get("/api/artifacts?artifact_type=brief")
        assert len(resp.json()) == 1
        assert resp.json()[0]["artifact_type"] == "brief"

    def test_filter_by_is_seedable(self, client):
        make_artifact(client, is_seedable=True)
        make_artifact(client, title="Non-seed", is_seedable=False)
        resp = client.get("/api/artifacts?is_seedable=true")
        assert len(resp.json()) == 1
        assert resp.json()[0]["is_seedable"] is True

    def test_filter_by_search(self, client):
        make_artifact(client, title="CLAUDE.md Org Standards")
        make_artifact(client, title="Agent Brief")
        resp = client.get("/api/artifacts?search=claude")
        assert len(resp.json()) == 1
        assert "CLAUDE" in resp.json()[0]["title"]

    def test_filter_by_parent_id(self, client):
        parent = make_artifact(client, title="Parent")
        child1 = make_artifact(client, title="Child 1", parent_id=parent["id"])
        make_artifact(client, title="Child 2", parent_id=parent["id"])
        make_artifact(client, title="Standalone")
        resp = client.get(f"/api/artifacts?parent_id={parent['id']}")
        children = resp.json()
        assert len(children) == 2

    def test_filter_by_tag(self, client):
        tag = make_tag(client, name="claude-md")
        a1 = make_artifact(client, title="Tagged", tag_ids=[tag["id"]])
        make_artifact(client, title="Untagged")
        resp = client.get("/api/artifacts?tag=claude-md")
        assert len(resp.json()) == 1
        assert resp.json()[0]["id"] == a1["id"]

    def test_filter_by_tag_and_logic(self, client):
        tag1 = make_tag(client, name="claude-md")
        tag2 = make_tag(client, name="org-level")
        a_both = make_artifact(client, title="Both Tags", tag_ids=[tag1["id"], tag2["id"]])
        make_artifact(client, title="One Tag", tag_ids=[tag1["id"]])
        resp = client.get("/api/artifacts?tag=claude-md,org-level")
        results = resp.json()
        assert len(results) == 1
        assert results[0]["id"] == a_both["id"]

    def test_filter_composable(self, client):
        tag = make_tag(client, name="proto")
        make_artifact(client, artifact_type="protocol", tag_ids=[tag["id"]])
        make_artifact(client, title="Doc", artifact_type="document", tag_ids=[tag["id"]])
        resp = client.get("/api/artifacts?artifact_type=protocol&tag=proto")
        assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# GET /api/artifacts/{id} — Detail (with content)
# ---------------------------------------------------------------------------

class TestGetArtifact:

    def test_get_returns_content(self, client):
        artifact = make_artifact(client, content="Full content here")
        resp = client.get(f"/api/artifacts/{artifact['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["content"] == "Full content here"
        assert body["title"] == "Test Artifact"

    def test_get_resolves_parent(self, client):
        parent = make_artifact(client, title="Part 1")
        child = make_artifact(client, title="Part 2", parent_id=parent["id"])
        resp = client.get(f"/api/artifacts/{child['id']}")
        body = resp.json()
        assert body["parent"] is not None
        assert body["parent"]["id"] == parent["id"]
        assert body["parent"]["title"] == "Part 1"
        assert "content" not in body["parent"]  # parent is ArtifactResponse, no content

    def test_get_without_parent(self, client):
        artifact = make_artifact(client)
        resp = client.get(f"/api/artifacts/{artifact['id']}")
        assert resp.json()["parent"] is None

    def test_get_not_found(self, client):
        resp = client.get(f"/api/artifacts/{FAKE_UUID}")
        assert resp.status_code == 404

    def test_get_includes_tags(self, client):
        tag = make_tag(client, name="test-tag")
        artifact = make_artifact(client, tag_ids=[tag["id"]])
        resp = client.get(f"/api/artifacts/{artifact['id']}")
        body = resp.json()
        assert len(body["tags"]) == 1
        assert body["tags"][0]["name"] == "test-tag"


# ---------------------------------------------------------------------------
# PATCH /api/artifacts/{id} — Update
# ---------------------------------------------------------------------------

class TestUpdateArtifact:

    def test_update_metadata_only(self, client):
        artifact = make_artifact(client)
        resp = client.patch(f"/api/artifacts/{artifact['id']}", json={
            "title": "Updated Title",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Updated Title"
        assert body["version"] == 1  # no content change — version stays

    def test_update_content_increments_version(self, client):
        artifact = make_artifact(client, content="v1 content")
        resp = client.patch(f"/api/artifacts/{artifact['id']}", json={
            "content": "v2 content",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == 2
        assert body["content"] == "v2 content"
        assert body["content_size"] == len("v2 content".encode("utf-8"))

    def test_update_content_twice(self, client):
        artifact = make_artifact(client)
        client.patch(f"/api/artifacts/{artifact['id']}", json={"content": "v2"})
        resp = client.patch(f"/api/artifacts/{artifact['id']}", json={"content": "v3"})
        assert resp.json()["version"] == 3

    def test_update_content_recomputes_size(self, client):
        artifact = make_artifact(client, content="short")
        new_content = "a much longer piece of content for testing"
        resp = client.patch(f"/api/artifacts/{artifact['id']}", json={
            "content": new_content,
        })
        assert resp.json()["content_size"] == len(new_content.encode("utf-8"))

    def test_update_parent_id(self, client):
        parent = make_artifact(client, title="New Parent")
        child = make_artifact(client, title="Child")
        resp = client.patch(f"/api/artifacts/{child['id']}", json={
            "parent_id": parent["id"],
        })
        assert resp.status_code == 200
        assert resp.json()["parent_id"] == parent["id"]

    def test_update_parent_id_invalid(self, client):
        artifact = make_artifact(client)
        resp = client.patch(f"/api/artifacts/{artifact['id']}", json={
            "parent_id": FAKE_UUID,
        })
        assert resp.status_code == 400

    def test_update_not_found(self, client):
        resp = client.patch(f"/api/artifacts/{FAKE_UUID}", json={"title": "Nope"})
        assert resp.status_code == 404

    def test_update_returns_detail_response(self, client):
        artifact = make_artifact(client, content="original")
        resp = client.patch(f"/api/artifacts/{artifact['id']}", json={
            "title": "Renamed",
        })
        body = resp.json()
        assert "content" in body  # detail response includes content
        assert body["content"] == "original"

    def test_update_artifact_type(self, client):
        artifact = make_artifact(client, artifact_type="document")
        resp = client.patch(f"/api/artifacts/{artifact['id']}", json={
            "artifact_type": "brief",
        })
        assert resp.json()["artifact_type"] == "brief"
        assert resp.json()["version"] == 1  # metadata-only, no version bump

    def test_update_is_seedable(self, client):
        artifact = make_artifact(client, is_seedable=False)
        resp = client.patch(f"/api/artifacts/{artifact['id']}", json={
            "is_seedable": True,
        })
        assert resp.json()["is_seedable"] is True


# ---------------------------------------------------------------------------
# DELETE /api/artifacts/{id}
# ---------------------------------------------------------------------------

class TestDeleteArtifact:

    def test_delete(self, client):
        artifact = make_artifact(client)
        resp = client.delete(f"/api/artifacts/{artifact['id']}")
        assert resp.status_code == 204
        resp = client.get(f"/api/artifacts/{artifact['id']}")
        assert resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete(f"/api/artifacts/{FAKE_UUID}")
        assert resp.status_code == 404

    def test_delete_parent_nulls_children(self, client):
        parent = make_artifact(client, title="Parent")
        child = make_artifact(client, title="Child", parent_id=parent["id"])
        client.delete(f"/api/artifacts/{parent['id']}")
        resp = client.get(f"/api/artifacts/{child['id']}")
        assert resp.status_code == 200
        assert resp.json()["parent_id"] is None
        assert resp.json()["parent"] is None


# ---------------------------------------------------------------------------
# Artifact-Tag attachment — /api/artifacts/{artifact_id}/tags
# ---------------------------------------------------------------------------

class TestArtifactTagAttach:

    def test_attach_tag(self, client):
        tag = make_tag(client, name="claude-md")
        artifact = make_artifact(client)
        resp = client.post(f"/api/artifacts/{artifact['id']}/tags/{tag['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == tag["id"]

    def test_attach_idempotent(self, client):
        tag = make_tag(client, name="claude-md")
        artifact = make_artifact(client)
        client.post(f"/api/artifacts/{artifact['id']}/tags/{tag['id']}")
        resp = client.post(f"/api/artifacts/{artifact['id']}/tags/{tag['id']}")
        assert resp.status_code == 200
        tags_resp = client.get(f"/api/artifacts/{artifact['id']}/tags")
        assert len(tags_resp.json()) == 1

    def test_attach_invalid_artifact(self, client):
        tag = make_tag(client, name="test")
        resp = client.post(f"/api/artifacts/{FAKE_UUID}/tags/{tag['id']}")
        assert resp.status_code == 404

    def test_attach_invalid_tag(self, client):
        artifact = make_artifact(client)
        resp = client.post(f"/api/artifacts/{artifact['id']}/tags/{FAKE_UUID}")
        assert resp.status_code == 404


class TestArtifactTagDetach:

    def test_detach_tag(self, client):
        tag = make_tag(client, name="claude-md")
        artifact = make_artifact(client)
        client.post(f"/api/artifacts/{artifact['id']}/tags/{tag['id']}")
        resp = client.delete(f"/api/artifacts/{artifact['id']}/tags/{tag['id']}")
        assert resp.status_code == 204

    def test_detach_invalid_artifact(self, client):
        tag = make_tag(client, name="test")
        resp = client.delete(f"/api/artifacts/{FAKE_UUID}/tags/{tag['id']}")
        assert resp.status_code == 404

    def test_detach_invalid_tag(self, client):
        artifact = make_artifact(client)
        resp = client.delete(f"/api/artifacts/{artifact['id']}/tags/{FAKE_UUID}")
        assert resp.status_code == 404

    def test_detach_not_attached(self, client):
        tag = make_tag(client, name="claude-md")
        artifact = make_artifact(client)
        resp = client.delete(f"/api/artifacts/{artifact['id']}/tags/{tag['id']}")
        assert resp.status_code == 404


class TestArtifactTagList:

    def test_list_tags_on_artifact(self, client):
        tag1 = make_tag(client, name="claude-md")
        tag2 = make_tag(client, name="org-level")
        artifact = make_artifact(client)
        client.post(f"/api/artifacts/{artifact['id']}/tags/{tag1['id']}")
        client.post(f"/api/artifacts/{artifact['id']}/tags/{tag2['id']}")
        resp = client.get(f"/api/artifacts/{artifact['id']}/tags")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_tags_empty(self, client):
        artifact = make_artifact(client)
        resp = client.get(f"/api/artifacts/{artifact['id']}/tags")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_tags_invalid_artifact(self, client):
        resp = client.get(f"/api/artifacts/{FAKE_UUID}/tags")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reverse lookup — GET /api/tags/{tag_id}/artifacts
# ---------------------------------------------------------------------------

class TestReverseArtifactLookup:

    def test_list_artifacts_for_tag(self, client):
        tag = make_tag(client, name="claude-md")
        a1 = make_artifact(client, title="Doc 1")
        a2 = make_artifact(client, title="Doc 2")
        client.post(f"/api/artifacts/{a1['id']}/tags/{tag['id']}")
        client.post(f"/api/artifacts/{a2['id']}/tags/{tag['id']}")
        resp = client.get(f"/api/tags/{tag['id']}/artifacts")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_reverse_lookup_empty(self, client):
        tag = make_tag(client, name="unused")
        resp = client.get(f"/api/tags/{tag['id']}/artifacts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_reverse_lookup_invalid_tag(self, client):
        resp = client.get(f"/api/tags/{FAKE_UUID}/artifacts")
        assert resp.status_code == 404

    def test_reverse_lookup_no_content(self, client):
        tag = make_tag(client, name="test")
        artifact = make_artifact(client, content="Should not appear")
        client.post(f"/api/artifacts/{artifact['id']}/tags/{tag['id']}")
        resp = client.get(f"/api/tags/{tag['id']}/artifacts")
        for item in resp.json():
            assert "content" not in item


# ---------------------------------------------------------------------------
# Cascade behavior
# ---------------------------------------------------------------------------

class TestArtifactCascade:

    def test_delete_tag_cascades_artifact_associations(self, client):
        tag = make_tag(client, name="temp")
        artifact = make_artifact(client)
        client.post(f"/api/artifacts/{artifact['id']}/tags/{tag['id']}")
        client.delete(f"/api/tags/{tag['id']}")
        resp = client.get(f"/api/artifacts/{artifact['id']}")
        assert resp.status_code == 200
        assert resp.json()["tags"] == []

    def test_delete_artifact_cascades_tag_associations(self, client):
        tag = make_tag(client, name="persist")
        artifact = make_artifact(client)
        client.post(f"/api/artifacts/{artifact['id']}/tags/{tag['id']}")
        client.delete(f"/api/artifacts/{artifact['id']}")
        resp = client.get(f"/api/tags/{tag['id']}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tags in artifact responses
# ---------------------------------------------------------------------------

class TestArtifactResponseIncludesTags:

    def test_list_response_includes_tags(self, client):
        tag = make_tag(client, name="claude-md")
        artifact = make_artifact(client, tag_ids=[tag["id"]])
        resp = client.get("/api/artifacts")
        items = resp.json()
        assert len(items) == 1
        assert len(items[0]["tags"]) == 1
        assert items[0]["tags"][0]["name"] == "claude-md"

    def test_detail_response_includes_tags(self, client):
        tag = make_tag(client, name="claude-md")
        artifact = make_artifact(client, tag_ids=[tag["id"]])
        resp = client.get(f"/api/artifacts/{artifact['id']}")
        body = resp.json()
        assert len(body["tags"]) == 1
        assert body["tags"][0]["name"] == "claude-md"
