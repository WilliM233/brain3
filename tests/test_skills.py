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

"""Tests for Skills — CRUD, is_default constraint, relationship management,
get_skill_full, cascade behavior, filters."""

import uuid

from tests.conftest import FAKE_UUID, make_domain

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_artifact(client, **overrides) -> dict:
    """Create an artifact via the API."""
    data = {
        "title": "Test Artifact",
        "artifact_type": "document",
        "content": "test content",
        **overrides,
    }
    resp = client.post("/api/artifacts", json=data)
    assert resp.status_code == 201
    return resp.json()


def make_protocol(client, **overrides) -> dict:
    """Create a protocol via the API."""
    data = {"name": f"proto-{uuid.uuid4().hex[:8]}", **overrides}
    resp = client.post("/api/protocols", json=data)
    assert resp.status_code == 201
    return resp.json()


def make_directive(client, **overrides) -> dict:
    """Create a directive via the API."""
    data = {
        "name": f"directive-{uuid.uuid4().hex[:8]}",
        "content": "Test directive content.",
        "scope": "global",
        **overrides,
    }
    resp = client.post("/api/directives", json=data)
    assert resp.status_code == 201
    return resp.json()


def make_skill(client, **overrides) -> dict:
    """Create a skill via the API."""
    data = {"name": f"skill-{uuid.uuid4().hex[:8]}", **overrides}
    resp = client.post("/api/skills", json=data)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/skills — Create
# ---------------------------------------------------------------------------


class TestCreateSkill:

    def test_create_minimal(self, client):
        resp = client.post("/api/skills", json={"name": "core-protocol"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "core-protocol"
        assert body["description"] is None
        assert body["adhd_patterns"] is None
        assert body["artifact_id"] is None
        assert body["is_seedable"] is True
        assert body["is_default"] is False
        assert body["domains"] == []
        assert body["protocols"] == []
        assert body["directives"] == []
        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body

    def test_create_with_all_fields(self, client):
        artifact = make_artifact(client)
        domain = make_domain(client, name="Engineering")
        protocol = make_protocol(client)
        directive = make_directive(client)

        resp = client.post("/api/skills", json={
            "name": "po-dev",
            "description": "Product owner / developer mode",
            "adhd_patterns": "Focus on one ticket at a time",
            "artifact_id": artifact["id"],
            "is_seedable": True,
            "is_default": True,
            "domain_ids": [domain["id"]],
            "protocol_ids": [protocol["id"]],
            "directive_ids": [directive["id"]],
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "po-dev"
        assert body["description"] == "Product owner / developer mode"
        assert body["adhd_patterns"] == "Focus on one ticket at a time"
        assert body["artifact_id"] == artifact["id"]
        assert body["is_default"] is True
        assert len(body["domains"]) == 1
        assert body["domains"][0]["id"] == domain["id"]
        assert len(body["protocols"]) == 1
        assert body["protocols"][0]["id"] == protocol["id"]
        assert len(body["directives"]) == 1
        assert body["directives"][0]["id"] == directive["id"]

    def test_create_duplicate_name_409(self, client):
        make_skill(client, name="duplicate")
        resp = client.post("/api/skills", json={"name": "duplicate"})
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    def test_create_invalid_artifact_400(self, client):
        resp = client.post("/api/skills", json={
            "name": "test",
            "artifact_id": FAKE_UUID,
        })
        assert resp.status_code == 400
        assert "Artifact not found" in resp.json()["detail"]

    def test_create_invalid_domain_400(self, client):
        resp = client.post("/api/skills", json={
            "name": "test",
            "domain_ids": [FAKE_UUID],
        })
        assert resp.status_code == 400
        assert "Domain" in resp.json()["detail"]

    def test_create_invalid_protocol_400(self, client):
        resp = client.post("/api/skills", json={
            "name": "test",
            "protocol_ids": [FAKE_UUID],
        })
        assert resp.status_code == 400
        assert "Protocol" in resp.json()["detail"]

    def test_create_invalid_directive_400(self, client):
        resp = client.post("/api/skills", json={
            "name": "test",
            "directive_ids": [FAKE_UUID],
        })
        assert resp.status_code == 400
        assert "Directive" in resp.json()["detail"]

    def test_create_second_default_409(self, client):
        make_skill(client, name="default-one", is_default=True)
        resp = client.post("/api/skills", json={
            "name": "default-two",
            "is_default": True,
        })
        assert resp.status_code == 409
        assert "already the default" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/skills — List
# ---------------------------------------------------------------------------


class TestListSkills:

    def test_list_empty(self, client):
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_all(self, client):
        make_skill(client, name="alpha")
        make_skill(client, name="beta")
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_includes_relationships(self, client):
        domain = make_domain(client)
        make_skill(client, name="with-domain", domain_ids=[domain["id"]])
        resp = client.get("/api/skills")
        body = resp.json()
        assert len(body) == 1
        assert len(body[0]["domains"]) == 1

    def test_filter_search(self, client):
        make_skill(client, name="core-protocol")
        make_skill(client, name="wellness")
        resp = client.get("/api/skills", params={"search": "core"})
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "core-protocol"

    def test_filter_is_seedable(self, client):
        make_skill(client, name="seedable", is_seedable=True)
        make_skill(client, name="not-seedable", is_seedable=False)
        resp = client.get("/api/skills", params={"is_seedable": True})
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "seedable"

    def test_filter_is_default(self, client):
        make_skill(client, name="default", is_default=True)
        make_skill(client, name="not-default")
        resp = client.get("/api/skills", params={"is_default": True})
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "default"

    def test_filter_domain_id(self, client):
        d1 = make_domain(client, name="D1")
        d2 = make_domain(client, name="D2")
        make_skill(client, name="has-d1", domain_ids=[d1["id"]])
        make_skill(client, name="has-d2", domain_ids=[d2["id"]])
        resp = client.get("/api/skills", params={"domain_id": d1["id"]})
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "has-d1"


# ---------------------------------------------------------------------------
# GET /api/skills/{id} — Detail
# ---------------------------------------------------------------------------


class TestGetSkill:

    def test_get_existing(self, client):
        skill = make_skill(client)
        resp = client.get(f"/api/skills/{skill['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == skill["id"]

    def test_get_not_found(self, client):
        resp = client.get(f"/api/skills/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/skills/{id}/full — Full resolved view
# ---------------------------------------------------------------------------


class TestGetSkillFull:

    def test_full_empty_skill(self, client):
        skill = make_skill(client)
        resp = client.get(f"/api/skills/{skill['id']}/full")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == skill["id"]
        assert body["domains"] == []
        assert body["protocols"] == []
        assert body["directives"]["global_directives"] == []
        assert body["directives"]["skill"] == []
        assert body["artifact"] is None

    def test_full_with_relationships(self, client):
        domain = make_domain(client)
        protocol = make_protocol(client)
        directive = make_directive(client, name="skill-dir", scope="global", priority=8)
        artifact = make_artifact(client)
        skill = make_skill(
            client,
            artifact_id=artifact["id"],
            domain_ids=[domain["id"]],
            protocol_ids=[protocol["id"]],
            directive_ids=[directive["id"]],
        )

        resp = client.get(f"/api/skills/{skill['id']}/full")
        assert resp.status_code == 200
        body = resp.json()

        assert len(body["domains"]) == 1
        assert body["domains"][0]["id"] == domain["id"]
        assert len(body["protocols"]) == 1
        assert body["protocols"][0]["id"] == protocol["id"]
        assert body["artifact"] is not None
        assert body["artifact"]["id"] == artifact["id"]

    def test_full_global_directives_always_included(self, client):
        """Global directives appear even if not linked to the skill."""
        global_d = make_directive(client, name="global-always", scope="global")
        skill = make_skill(client)

        resp = client.get(f"/api/skills/{skill['id']}/full")
        body = resp.json()
        global_ids = [d["id"] for d in body["directives"]["global_directives"]]
        assert global_d["id"] in global_ids

    def test_full_directives_grouped(self, client):
        """Skill-linked directives appear in 'skill' group, globals in 'global_directives'."""
        global_d = make_directive(client, name="global-one", scope="global", priority=3)
        skill_d = make_directive(client, name="skill-one", scope="global", priority=7)

        skill = make_skill(client, directive_ids=[skill_d["id"]])

        resp = client.get(f"/api/skills/{skill['id']}/full")
        body = resp.json()

        skill_group_ids = [d["id"] for d in body["directives"]["skill"]]
        assert skill_d["id"] in skill_group_ids

        global_group_ids = [d["id"] for d in body["directives"]["global_directives"]]
        assert global_d["id"] in global_group_ids

    def test_full_directives_sorted_by_priority_desc(self, client):
        """Directives in each group are sorted by priority descending."""
        d_low = make_directive(client, name="low-pri", scope="global", priority=2)
        d_high = make_directive(client, name="high-pri", scope="global", priority=9)

        skill = make_skill(client, directive_ids=[d_low["id"], d_high["id"]])

        resp = client.get(f"/api/skills/{skill['id']}/full")
        body = resp.json()

        skill_priorities = [d["priority"] for d in body["directives"]["skill"]]
        assert skill_priorities == sorted(skill_priorities, reverse=True)

        global_priorities = [d["priority"] for d in body["directives"]["global_directives"]]
        assert global_priorities == sorted(global_priorities, reverse=True)

    def test_full_not_found(self, client):
        resp = client.get(f"/api/skills/{FAKE_UUID}/full")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/skills/{id} — Update
# ---------------------------------------------------------------------------


class TestUpdateSkill:

    def test_update_name(self, client):
        skill = make_skill(client, name="old-name")
        resp = client.patch(f"/api/skills/{skill['id']}", json={"name": "new-name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "new-name"

    def test_update_description(self, client):
        skill = make_skill(client)
        resp = client.patch(
            f"/api/skills/{skill['id']}", json={"description": "Updated desc"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated desc"

    def test_update_duplicate_name_409(self, client):
        make_skill(client, name="existing")
        skill = make_skill(client, name="other")
        resp = client.patch(f"/api/skills/{skill['id']}", json={"name": "existing"})
        assert resp.status_code == 409

    def test_update_same_name_ok(self, client):
        skill = make_skill(client, name="keep-this")
        resp = client.patch(f"/api/skills/{skill['id']}", json={"name": "keep-this"})
        assert resp.status_code == 200

    def test_update_is_default_conflict(self, client):
        make_skill(client, name="default-one", is_default=True)
        skill = make_skill(client, name="not-default")
        resp = client.patch(f"/api/skills/{skill['id']}", json={"is_default": True})
        assert resp.status_code == 409

    def test_update_is_default_same_skill_ok(self, client):
        skill = make_skill(client, name="the-default", is_default=True)
        resp = client.patch(
            f"/api/skills/{skill['id']}",
            json={"is_default": True, "description": "still default"},
        )
        assert resp.status_code == 200

    def test_update_invalid_artifact_400(self, client):
        skill = make_skill(client)
        resp = client.patch(
            f"/api/skills/{skill['id']}", json={"artifact_id": FAKE_UUID},
        )
        assert resp.status_code == 400

    def test_update_not_found(self, client):
        resp = client.patch(f"/api/skills/{FAKE_UUID}", json={"name": "nope"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/skills/{id}
# ---------------------------------------------------------------------------


class TestDeleteSkill:

    def test_delete_existing(self, client):
        skill = make_skill(client)
        resp = client.delete(f"/api/skills/{skill['id']}")
        assert resp.status_code == 204

        resp = client.get(f"/api/skills/{skill['id']}")
        assert resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete(f"/api/skills/{FAKE_UUID}")
        assert resp.status_code == 404

    def test_delete_cascades_to_join_tables(self, client):
        """Deleting a skill removes its join table entries but not the linked entities."""
        domain = make_domain(client)
        protocol = make_protocol(client)
        directive = make_directive(client)

        skill = make_skill(
            client,
            domain_ids=[domain["id"]],
            protocol_ids=[protocol["id"]],
            directive_ids=[directive["id"]],
        )
        client.delete(f"/api/skills/{skill['id']}")

        # Linked entities still exist
        assert client.get(f"/api/domains/{domain['id']}").status_code == 200
        assert client.get(f"/api/protocols/{protocol['id']}").status_code == 200
        assert client.get(f"/api/directives/{directive['id']}").status_code == 200


# ---------------------------------------------------------------------------
# Relationship management — Domains
# ---------------------------------------------------------------------------


class TestSkillDomains:

    def test_list_domains_empty(self, client):
        skill = make_skill(client)
        resp = client.get(f"/api/skills/{skill['id']}/domains")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_link_domain(self, client):
        skill = make_skill(client)
        domain = make_domain(client)
        resp = client.post(f"/api/skills/{skill['id']}/domains/{domain['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == domain["id"]

        # Verify in list
        resp = client.get(f"/api/skills/{skill['id']}/domains")
        assert len(resp.json()) == 1

    def test_link_domain_idempotent(self, client):
        skill = make_skill(client)
        domain = make_domain(client)
        client.post(f"/api/skills/{skill['id']}/domains/{domain['id']}")
        client.post(f"/api/skills/{skill['id']}/domains/{domain['id']}")
        resp = client.get(f"/api/skills/{skill['id']}/domains")
        assert len(resp.json()) == 1

    def test_unlink_domain(self, client):
        skill = make_skill(client)
        domain = make_domain(client)
        client.post(f"/api/skills/{skill['id']}/domains/{domain['id']}")
        resp = client.delete(f"/api/skills/{skill['id']}/domains/{domain['id']}")
        assert resp.status_code == 204

        resp = client.get(f"/api/skills/{skill['id']}/domains")
        assert len(resp.json()) == 0

    def test_unlink_domain_not_linked_404(self, client):
        skill = make_skill(client)
        domain = make_domain(client)
        resp = client.delete(f"/api/skills/{skill['id']}/domains/{domain['id']}")
        assert resp.status_code == 404

    def test_link_domain_skill_not_found(self, client):
        domain = make_domain(client)
        resp = client.post(f"/api/skills/{FAKE_UUID}/domains/{domain['id']}")
        assert resp.status_code == 404

    def test_link_domain_not_found(self, client):
        skill = make_skill(client)
        resp = client.post(f"/api/skills/{skill['id']}/domains/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Relationship management — Protocols
# ---------------------------------------------------------------------------


class TestSkillProtocols:

    def test_list_protocols_empty(self, client):
        skill = make_skill(client)
        resp = client.get(f"/api/skills/{skill['id']}/protocols")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_link_protocol(self, client):
        skill = make_skill(client)
        protocol = make_protocol(client)
        resp = client.post(f"/api/skills/{skill['id']}/protocols/{protocol['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == protocol["id"]

    def test_link_protocol_idempotent(self, client):
        skill = make_skill(client)
        protocol = make_protocol(client)
        client.post(f"/api/skills/{skill['id']}/protocols/{protocol['id']}")
        client.post(f"/api/skills/{skill['id']}/protocols/{protocol['id']}")
        resp = client.get(f"/api/skills/{skill['id']}/protocols")
        assert len(resp.json()) == 1

    def test_unlink_protocol(self, client):
        skill = make_skill(client)
        protocol = make_protocol(client)
        client.post(f"/api/skills/{skill['id']}/protocols/{protocol['id']}")
        resp = client.delete(f"/api/skills/{skill['id']}/protocols/{protocol['id']}")
        assert resp.status_code == 204

    def test_unlink_protocol_not_linked_404(self, client):
        skill = make_skill(client)
        protocol = make_protocol(client)
        resp = client.delete(f"/api/skills/{skill['id']}/protocols/{protocol['id']}")
        assert resp.status_code == 404

    def test_link_protocol_skill_not_found(self, client):
        protocol = make_protocol(client)
        resp = client.post(f"/api/skills/{FAKE_UUID}/protocols/{protocol['id']}")
        assert resp.status_code == 404

    def test_link_protocol_not_found(self, client):
        skill = make_skill(client)
        resp = client.post(f"/api/skills/{skill['id']}/protocols/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Relationship management — Directives
# ---------------------------------------------------------------------------


class TestSkillDirectives:

    def test_list_directives_empty(self, client):
        skill = make_skill(client)
        resp = client.get(f"/api/skills/{skill['id']}/directives")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_link_directive(self, client):
        skill = make_skill(client)
        directive = make_directive(client)
        resp = client.post(f"/api/skills/{skill['id']}/directives/{directive['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == directive["id"]

    def test_link_directive_idempotent(self, client):
        skill = make_skill(client)
        directive = make_directive(client)
        client.post(f"/api/skills/{skill['id']}/directives/{directive['id']}")
        client.post(f"/api/skills/{skill['id']}/directives/{directive['id']}")
        resp = client.get(f"/api/skills/{skill['id']}/directives")
        assert len(resp.json()) == 1

    def test_unlink_directive(self, client):
        skill = make_skill(client)
        directive = make_directive(client)
        client.post(f"/api/skills/{skill['id']}/directives/{directive['id']}")
        resp = client.delete(f"/api/skills/{skill['id']}/directives/{directive['id']}")
        assert resp.status_code == 204

    def test_unlink_directive_not_linked_404(self, client):
        skill = make_skill(client)
        directive = make_directive(client)
        resp = client.delete(f"/api/skills/{skill['id']}/directives/{directive['id']}")
        assert resp.status_code == 404

    def test_link_directive_skill_not_found(self, client):
        directive = make_directive(client)
        resp = client.post(f"/api/skills/{FAKE_UUID}/directives/{directive['id']}")
        assert resp.status_code == 404

    def test_link_directive_not_found(self, client):
        skill = make_skill(client)
        resp = client.post(f"/api/skills/{skill['id']}/directives/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cascade from related entity deletion
# ---------------------------------------------------------------------------


class TestCascadeFromRelatedDeletion:

    def test_deleting_domain_removes_join_entry(self, client):
        """Deleting a domain cascades to skill_domains."""
        domain = make_domain(client)
        skill = make_skill(client, domain_ids=[domain["id"]])

        client.delete(f"/api/domains/{domain['id']}")

        resp = client.get(f"/api/skills/{skill['id']}/domains")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_deleting_protocol_removes_join_entry(self, client):
        """Deleting a protocol cascades to skill_protocols."""
        protocol = make_protocol(client)
        skill = make_skill(client, protocol_ids=[protocol["id"]])

        client.delete(f"/api/protocols/{protocol['id']}")

        resp = client.get(f"/api/skills/{skill['id']}/protocols")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_deleting_directive_removes_join_entry(self, client):
        """Deleting a directive cascades to skill_directives."""
        directive = make_directive(client)
        skill = make_skill(client, directive_ids=[directive["id"]])

        client.delete(f"/api/directives/{directive['id']}")

        resp = client.get(f"/api/skills/{skill['id']}/directives")
        assert resp.status_code == 200
        assert len(resp.json()) == 0
