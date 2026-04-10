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

"""Tests for Directives — CRUD, scope validation, resolve endpoint, tagging, filters."""

import uuid

from tests.conftest import FAKE_UUID, make_tag

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SKILL_UUID = str(uuid.uuid4())
AGENT_UUID = str(uuid.uuid4())


def make_directive(client, **overrides) -> dict:
    """Create a directive via the API and return the response JSON."""
    data = {
        "name": "test-directive",
        "content": "This is a test directive.",
        "scope": "global",
        **overrides,
    }
    resp = client.post("/api/directives", json=data)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/directives — Create
# ---------------------------------------------------------------------------

class TestCreateDirective:

    def test_create_global_minimal(self, client):
        resp = client.post("/api/directives", json={
            "name": "low friction",
            "content": "Low friction is a design requirement.",
            "scope": "global",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "low friction"
        assert body["content"] == "Low friction is a design requirement."
        assert body["scope"] == "global"
        assert body["scope_ref"] is None
        assert body["priority"] == 5
        assert body["is_seedable"] is True
        assert body["tags"] == []

    def test_create_skill_scoped(self, client):
        resp = client.post("/api/directives", json={
            "name": "skill directive",
            "content": "Applies to a specific skill.",
            "scope": "skill",
            "scope_ref": SKILL_UUID,
            "priority": 8,
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["scope"] == "skill"
        assert body["scope_ref"] == SKILL_UUID
        assert body["priority"] == 8

    def test_create_agent_scoped(self, client):
        resp = client.post("/api/directives", json={
            "name": "agent directive",
            "content": "Agent-specific guardrail.",
            "scope": "agent",
            "scope_ref": AGENT_UUID,
        })
        assert resp.status_code == 201
        assert resp.json()["scope"] == "agent"
        assert resp.json()["scope_ref"] == AGENT_UUID

    def test_create_with_all_fields(self, client):
        tag = make_tag(client, name="guardrail")
        resp = client.post("/api/directives", json={
            "name": "full directive",
            "content": "A fully specified directive.",
            "scope": "skill",
            "scope_ref": SKILL_UUID,
            "priority": 10,
            "is_seedable": False,
            "tag_ids": [tag["id"]],
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["is_seedable"] is False
        assert body["priority"] == 10
        assert len(body["tags"]) == 1
        assert body["tags"][0]["name"] == "guardrail"

    def test_create_global_with_scope_ref_fails(self, client):
        resp = client.post("/api/directives", json={
            "name": "bad global",
            "content": "Should fail.",
            "scope": "global",
            "scope_ref": SKILL_UUID,
        })
        assert resp.status_code == 422

    def test_create_skill_without_scope_ref_fails(self, client):
        resp = client.post("/api/directives", json={
            "name": "bad skill",
            "content": "Should fail.",
            "scope": "skill",
        })
        assert resp.status_code == 422

    def test_create_agent_without_scope_ref_fails(self, client):
        resp = client.post("/api/directives", json={
            "name": "bad agent",
            "content": "Should fail.",
            "scope": "agent",
        })
        assert resp.status_code == 422

    def test_create_invalid_scope_fails(self, client):
        resp = client.post("/api/directives", json={
            "name": "bad scope",
            "content": "Should fail.",
            "scope": "invalid",
        })
        assert resp.status_code == 422

    def test_create_priority_below_range(self, client):
        resp = client.post("/api/directives", json={
            "name": "low priority",
            "content": "Should fail.",
            "scope": "global",
            "priority": 0,
        })
        assert resp.status_code == 422

    def test_create_priority_above_range(self, client):
        resp = client.post("/api/directives", json={
            "name": "high priority",
            "content": "Should fail.",
            "scope": "global",
            "priority": 11,
        })
        assert resp.status_code == 422

    def test_create_with_invalid_tag_id(self, client):
        resp = client.post("/api/directives", json={
            "name": "bad tag",
            "content": "Should fail.",
            "scope": "global",
            "tag_ids": [FAKE_UUID],
        })
        assert resp.status_code == 400

    def test_create_duplicate_name_allowed(self, client):
        """Directive names are NOT unique — multiple can share a name."""
        make_directive(client, name="shared-name")
        resp = client.post("/api/directives", json={
            "name": "shared-name",
            "content": "Same name, different directive.",
            "scope": "global",
        })
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/directives — List
# ---------------------------------------------------------------------------

class TestListDirectives:

    def test_list_empty(self, client):
        resp = client.get("/api/directives")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_all(self, client):
        make_directive(client, name="alpha")
        make_directive(client, name="beta")
        resp = client.get("/api/directives")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_filter_scope(self, client):
        make_directive(client, name="global-d", scope="global")
        make_directive(client, name="skill-d", scope="skill", scope_ref=SKILL_UUID)
        resp = client.get("/api/directives", params={"scope": "global"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "global-d"

    def test_list_filter_scope_ref(self, client):
        make_directive(client, name="s1", scope="skill", scope_ref=SKILL_UUID)
        make_directive(client, name="s2", scope="agent", scope_ref=AGENT_UUID)
        resp = client.get("/api/directives", params={"scope_ref": SKILL_UUID})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "s1"

    def test_list_filter_is_seedable(self, client):
        make_directive(client, name="seedable", is_seedable=True)
        make_directive(client, name="not-seedable", is_seedable=False)
        resp = client.get("/api/directives", params={"is_seedable": True})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "seedable"

    def test_list_filter_priority_min(self, client):
        make_directive(client, name="low", priority=2)
        make_directive(client, name="high", priority=8)
        resp = client.get("/api/directives", params={"priority_min": 5})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "high"

    def test_list_filter_priority_max(self, client):
        make_directive(client, name="low", priority=2)
        make_directive(client, name="high", priority=8)
        resp = client.get("/api/directives", params={"priority_max": 5})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "low"

    def test_list_filter_priority_range(self, client):
        make_directive(client, name="low", priority=2)
        make_directive(client, name="mid", priority=5)
        make_directive(client, name="high", priority=8)
        resp = client.get("/api/directives", params={"priority_min": 3, "priority_max": 7})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "mid"

    def test_list_filter_search(self, client):
        make_directive(client, name="low friction")
        make_directive(client, name="graduated scaffolding")
        resp = client.get("/api/directives", params={"search": "friction"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "low friction"

    def test_list_filter_search_case_insensitive(self, client):
        make_directive(client, name="Low Friction")
        resp = client.get("/api/directives", params={"search": "low"})
        assert len(resp.json()) == 1

    def test_list_filter_tag(self, client):
        tag = make_tag(client, name="core")
        d = make_directive(client, name="tagged")
        client.post(f"/api/directives/{d['id']}/tags/{tag['id']}")
        make_directive(client, name="untagged")
        resp = client.get("/api/directives", params={"tag": "core"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "tagged"

    def test_list_filter_tag_and_logic(self, client):
        tag1 = make_tag(client, name="core")
        tag2 = make_tag(client, name="guardrail")
        d = make_directive(client, name="both-tags")
        client.post(f"/api/directives/{d['id']}/tags/{tag1['id']}")
        client.post(f"/api/directives/{d['id']}/tags/{tag2['id']}")
        d2 = make_directive(client, name="one-tag")
        client.post(f"/api/directives/{d2['id']}/tags/{tag1['id']}")
        resp = client.get("/api/directives", params={"tag": "core,guardrail"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "both-tags"


# ---------------------------------------------------------------------------
# GET /api/directives/{id} — Detail
# ---------------------------------------------------------------------------

class TestGetDirective:

    def test_get_directive(self, client):
        d = make_directive(client, name="get-me")
        resp = client.get(f"/api/directives/{d['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "get-me"

    def test_get_directive_not_found(self, client):
        resp = client.get(f"/api/directives/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/directives/{id} — Update
# ---------------------------------------------------------------------------

class TestUpdateDirective:

    def test_update_name(self, client):
        d = make_directive(client, name="old-name")
        resp = client.patch(f"/api/directives/{d['id']}", json={"name": "new-name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "new-name"

    def test_update_content(self, client):
        d = make_directive(client, name="update-content")
        resp = client.patch(f"/api/directives/{d['id']}", json={"content": "Updated."})
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated."

    def test_update_priority(self, client):
        d = make_directive(client, name="update-priority")
        resp = client.patch(f"/api/directives/{d['id']}", json={"priority": 10})
        assert resp.status_code == 200
        assert resp.json()["priority"] == 10

    def test_update_is_seedable(self, client):
        d = make_directive(client, name="update-seedable")
        resp = client.patch(f"/api/directives/{d['id']}", json={"is_seedable": False})
        assert resp.status_code == 200
        assert resp.json()["is_seedable"] is False

    def test_update_scope_with_scope_ref(self, client):
        """Change from global to skill — must also provide scope_ref."""
        d = make_directive(client, name="scope-change")
        resp = client.patch(f"/api/directives/{d['id']}", json={
            "scope": "skill",
            "scope_ref": SKILL_UUID,
        })
        assert resp.status_code == 200
        assert resp.json()["scope"] == "skill"
        assert resp.json()["scope_ref"] == SKILL_UUID

    def test_update_scope_to_global_clears_scope_ref(self, client):
        """Change from skill to global — must also clear scope_ref."""
        d = make_directive(
            client, name="clear-ref", scope="skill", scope_ref=SKILL_UUID,
        )
        resp = client.patch(f"/api/directives/{d['id']}", json={
            "scope": "global",
            "scope_ref": None,
        })
        assert resp.status_code == 200
        assert resp.json()["scope"] == "global"
        assert resp.json()["scope_ref"] is None

    def test_update_scope_to_skill_without_ref_fails(self, client):
        """Post-merge: scope=skill but no scope_ref should fail."""
        d = make_directive(client, name="bad-scope-update")
        resp = client.patch(f"/api/directives/{d['id']}", json={"scope": "skill"})
        assert resp.status_code == 422

    def test_update_global_adding_scope_ref_fails(self, client):
        """Post-merge: scope=global with scope_ref should fail."""
        d = make_directive(client, name="bad-ref-update")
        resp = client.patch(f"/api/directives/{d['id']}", json={"scope_ref": SKILL_UUID})
        assert resp.status_code == 422

    def test_update_not_found(self, client):
        resp = client.patch(f"/api/directives/{FAKE_UUID}", json={"name": "x"})
        assert resp.status_code == 404

    def test_update_priority_out_of_range(self, client):
        d = make_directive(client, name="bad-priority")
        resp = client.patch(f"/api/directives/{d['id']}", json={"priority": 11})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/directives/{id}
# ---------------------------------------------------------------------------

class TestDeleteDirective:

    def test_delete(self, client):
        d = make_directive(client, name="delete-me")
        resp = client.delete(f"/api/directives/{d['id']}")
        assert resp.status_code == 204
        assert client.get(f"/api/directives/{d['id']}").status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete(f"/api/directives/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/directives/resolve — Resolve endpoint
# ---------------------------------------------------------------------------

class TestResolveDirectives:

    def test_resolve_global_only(self, client):
        make_directive(client, name="g1", priority=8)
        make_directive(client, name="g2", priority=3)
        resp = client.get("/api/directives/resolve")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["global_directives"]) == 2
        assert body["skill_directives"] == []
        assert body["agent_directives"] == []
        # Sorted by priority desc
        assert body["global_directives"][0]["name"] == "g1"
        assert body["global_directives"][1]["name"] == "g2"

    def test_resolve_with_skill_id(self, client):
        make_directive(client, name="global-d")
        make_directive(
            client, name="skill-d", scope="skill",
            scope_ref=SKILL_UUID, priority=7,
        )
        # Directive for a different skill — should not appear
        other_skill = str(uuid.uuid4())
        make_directive(
            client, name="other-skill-d", scope="skill",
            scope_ref=other_skill,
        )
        resp = client.get("/api/directives/resolve", params={"skill_id": SKILL_UUID})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["global_directives"]) == 1
        assert len(body["skill_directives"]) == 1
        assert body["skill_directives"][0]["name"] == "skill-d"
        assert body["agent_directives"] == []

    def test_resolve_with_scope_ref(self, client):
        make_directive(client, name="global-d")
        make_directive(
            client, name="agent-d", scope="agent",
            scope_ref=AGENT_UUID, priority=9,
        )
        resp = client.get("/api/directives/resolve", params={"scope_ref": AGENT_UUID})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["global_directives"]) == 1
        assert len(body["agent_directives"]) == 1
        assert body["agent_directives"][0]["name"] == "agent-d"

    def test_resolve_all_scopes(self, client):
        make_directive(client, name="g", priority=5)
        make_directive(
            client, name="s", scope="skill",
            scope_ref=SKILL_UUID, priority=8,
        )
        make_directive(
            client, name="a", scope="agent",
            scope_ref=AGENT_UUID, priority=10,
        )
        resp = client.get("/api/directives/resolve", params={
            "skill_id": SKILL_UUID,
            "scope_ref": AGENT_UUID,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["global_directives"]) == 1
        assert len(body["skill_directives"]) == 1
        assert len(body["agent_directives"]) == 1

    def test_resolve_sorted_by_priority_desc(self, client):
        make_directive(client, name="low", priority=1)
        make_directive(client, name="mid", priority=5)
        make_directive(client, name="high", priority=10)
        resp = client.get("/api/directives/resolve")
        body = resp.json()
        priorities = [d["priority"] for d in body["global_directives"]]
        assert priorities == [10, 5, 1]

    def test_resolve_empty(self, client):
        resp = client.get("/api/directives/resolve")
        assert resp.status_code == 200
        body = resp.json()
        assert body["global_directives"] == []
        assert body["skill_directives"] == []
        assert body["agent_directives"] == []


# ---------------------------------------------------------------------------
# Directive-Tag attachment
# ---------------------------------------------------------------------------

class TestDirectiveTagging:

    def test_attach_tag(self, client):
        d = make_directive(client, name="tag-test")
        tag = make_tag(client, name="core")
        resp = client.post(f"/api/directives/{d['id']}/tags/{tag['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "core"

    def test_attach_tag_idempotent(self, client):
        d = make_directive(client, name="idem-test")
        tag = make_tag(client, name="core")
        client.post(f"/api/directives/{d['id']}/tags/{tag['id']}")
        resp = client.post(f"/api/directives/{d['id']}/tags/{tag['id']}")
        assert resp.status_code == 200
        tags_resp = client.get(f"/api/directives/{d['id']}/tags")
        assert len(tags_resp.json()) == 1

    def test_list_tags_on_directive(self, client):
        d = make_directive(client, name="list-tags")
        tag1 = make_tag(client, name="alpha")
        tag2 = make_tag(client, name="beta")
        client.post(f"/api/directives/{d['id']}/tags/{tag1['id']}")
        client.post(f"/api/directives/{d['id']}/tags/{tag2['id']}")
        resp = client.get(f"/api/directives/{d['id']}/tags")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_detach_tag(self, client):
        d = make_directive(client, name="detach-test")
        tag = make_tag(client, name="remove-me")
        client.post(f"/api/directives/{d['id']}/tags/{tag['id']}")
        resp = client.delete(f"/api/directives/{d['id']}/tags/{tag['id']}")
        assert resp.status_code == 204
        tags_resp = client.get(f"/api/directives/{d['id']}/tags")
        assert len(tags_resp.json()) == 0

    def test_detach_tag_not_attached(self, client):
        d = make_directive(client, name="not-attached")
        tag = make_tag(client, name="loose")
        resp = client.delete(f"/api/directives/{d['id']}/tags/{tag['id']}")
        assert resp.status_code == 404

    def test_attach_tag_directive_not_found(self, client):
        tag = make_tag(client, name="orphan")
        resp = client.post(f"/api/directives/{FAKE_UUID}/tags/{tag['id']}")
        assert resp.status_code == 404

    def test_attach_tag_tag_not_found(self, client):
        d = make_directive(client, name="no-tag")
        resp = client.post(f"/api/directives/{d['id']}/tags/{FAKE_UUID}")
        assert resp.status_code == 404

    def test_list_tags_directive_not_found(self, client):
        resp = client.get(f"/api/directives/{FAKE_UUID}/tags")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reverse lookup — /api/tags/{tag_id}/directives
# ---------------------------------------------------------------------------

class TestTagReverseDirectives:

    def test_reverse_lookup(self, client):
        tag = make_tag(client, name="reverse-test")
        d = make_directive(client, name="reverse-d")
        client.post(f"/api/directives/{d['id']}/tags/{tag['id']}")
        resp = client.get(f"/api/tags/{tag['id']}/directives")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "reverse-d"

    def test_reverse_lookup_empty(self, client):
        tag = make_tag(client, name="empty-reverse")
        resp = client.get(f"/api/tags/{tag['id']}/directives")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_reverse_lookup_tag_not_found(self, client):
        resp = client.get(f"/api/tags/{FAKE_UUID}/directives")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# tag_ids on create
# ---------------------------------------------------------------------------

class TestCreateWithTagIds:

    def test_tag_ids_on_create(self, client):
        tag1 = make_tag(client, name="t1")
        tag2 = make_tag(client, name="t2")
        resp = client.post("/api/directives", json={
            "name": "tagged-create",
            "content": "Tagged at creation.",
            "scope": "global",
            "tag_ids": [tag1["id"], tag2["id"]],
        })
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["tags"]) == 2
        tag_names = {t["name"] for t in body["tags"]}
        assert tag_names == {"t1", "t2"}
