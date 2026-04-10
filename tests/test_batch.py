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

"""Tests for batch create and batch tag attachment endpoints."""

import uuid

from tests.conftest import (
    FAKE_UUID,
    make_activity,
    make_artifact,
    make_domain,
    make_protocol,
    make_tag,
    make_task,
)

# ---------------------------------------------------------------------------
# Batch Create — Tasks
# ---------------------------------------------------------------------------


class TestBatchCreateTasks:
    def test_happy_path(self, client):
        items = [{"title": f"Task {i}"} for i in range(3)]
        resp = client.post("/api/tasks/batch", json={"items": items})
        assert resp.status_code == 201
        body = resp.json()
        assert body["count"] == 3
        assert len(body["created"]) == 3
        assert body["created"][0]["title"] == "Task 0"
        assert body["created"][2]["title"] == "Task 2"

    def test_empty_batch(self, client):
        resp = client.post("/api/tasks/batch", json={"items": []})
        assert resp.status_code == 201
        body = resp.json()
        assert body == {"created": [], "count": 0}

    def test_max_size_exceeded(self, client):
        items = [{"title": f"Task {i}"} for i in range(101)]
        resp = client.post("/api/tasks/batch", json={"items": items})
        assert resp.status_code == 422

    def test_fk_validation_failure(self, client):
        items = [
            {"title": "Good task"},
            {"title": "Bad task", "project_id": FAKE_UUID},
        ]
        resp = client.post("/api/tasks/batch", json={"items": items})
        assert resp.status_code == 400
        assert "Batch item 1" in resp.json()["detail"]
        assert "Project not found" in resp.json()["detail"]

    def test_partial_failure_rolls_back(self, client):
        """No tasks created when one fails FK validation."""
        items = [
            {"title": "Should not persist"},
            {"title": "Bad task", "project_id": FAKE_UUID},
        ]
        client.post("/api/tasks/batch", json={"items": items})
        # Verify nothing was created
        resp = client.get("/api/tasks")
        assert resp.json() == []

    def test_with_project_id(self, client):
        domain = make_domain(client)
        from tests.conftest import make_goal, make_project

        goal = make_goal(client, domain["id"])
        project = make_project(client, goal["id"])

        items = [{"title": "Task in project", "project_id": project["id"]}]
        resp = client.post("/api/tasks/batch", json={"items": items})
        assert resp.status_code == 201
        assert resp.json()["created"][0]["project_id"] == project["id"]

    def test_preserves_order(self, client):
        items = [{"title": f"Ordered-{i}"} for i in range(5)]
        resp = client.post("/api/tasks/batch", json={"items": items})
        assert resp.status_code == 201
        titles = [t["title"] for t in resp.json()["created"]]
        assert titles == [f"Ordered-{i}" for i in range(5)]

    def test_existing_single_create_unchanged(self, client):
        resp = client.post("/api/tasks", json={"title": "Solo task"})
        assert resp.status_code == 201
        assert resp.json()["title"] == "Solo task"


# ---------------------------------------------------------------------------
# Batch Create — Activity Logs
# ---------------------------------------------------------------------------


class TestBatchCreateActivity:
    def test_happy_path(self, client):
        items = [{"action_type": "completed", "notes": f"Note {i}"} for i in range(3)]
        resp = client.post("/api/activity/batch", json={"items": items})
        assert resp.status_code == 201
        body = resp.json()
        assert body["count"] == 3

    def test_empty_batch(self, client):
        resp = client.post("/api/activity/batch", json={"items": []})
        assert resp.status_code == 201
        assert resp.json() == {"created": [], "count": 0}

    def test_with_tag_ids(self, client):
        tag1 = make_tag(client, name="batch-tag-1")
        tag2 = make_tag(client, name="batch-tag-2")
        items = [
            {
                "action_type": "reflected",
                "tag_ids": [tag1["id"], tag2["id"]],
            },
        ]
        resp = client.post("/api/activity/batch", json={"items": items})
        assert resp.status_code == 201
        entry = resp.json()["created"][0]
        tag_names = {t["name"] for t in entry["tags"]}
        assert "batch-tag-1" in tag_names
        assert "batch-tag-2" in tag_names

    def test_fk_validation_task(self, client):
        items = [{"action_type": "completed", "task_id": FAKE_UUID}]
        resp = client.post("/api/activity/batch", json={"items": items})
        assert resp.status_code == 400
        assert "Batch item 0" in resp.json()["detail"]
        assert "Task not found" in resp.json()["detail"]

    def test_fk_validation_tag(self, client):
        items = [{"action_type": "completed", "tag_ids": [FAKE_UUID]}]
        resp = client.post("/api/activity/batch", json={"items": items})
        assert resp.status_code == 400
        assert "Batch item 0" in resp.json()["detail"]

    def test_partial_failure_rolls_back(self, client):
        items = [
            {"action_type": "completed"},
            {"action_type": "completed", "task_id": FAKE_UUID},
        ]
        client.post("/api/activity/batch", json={"items": items})
        resp = client.get("/api/activity")
        assert resp.json() == []

    def test_max_size_exceeded(self, client):
        items = [{"action_type": "completed"} for _ in range(101)]
        resp = client.post("/api/activity/batch", json={"items": items})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Batch Create — Artifacts
# ---------------------------------------------------------------------------


class TestBatchCreateArtifacts:
    def test_happy_path(self, client):
        items = [
            {"title": f"Art {i}", "artifact_type": "prompt", "content": f"Content {i}"}
            for i in range(3)
        ]
        resp = client.post("/api/artifacts/batch", json={"items": items})
        assert resp.status_code == 201
        body = resp.json()
        assert body["count"] == 3
        assert body["created"][0]["content_size"] > 0

    def test_empty_batch(self, client):
        resp = client.post("/api/artifacts/batch", json={"items": []})
        assert resp.status_code == 201
        assert resp.json() == {"created": [], "count": 0}

    def test_with_tag_ids(self, client):
        tag = make_tag(client, name="art-tag")
        items = [
            {
                "title": "Tagged artifact",
                "artifact_type": "template",
                "content": "Hello",
                "tag_ids": [tag["id"]],
            },
        ]
        resp = client.post("/api/artifacts/batch", json={"items": items})
        assert resp.status_code == 201
        assert resp.json()["created"][0]["tags"][0]["name"] == "art-tag"

    def test_fk_validation_parent(self, client):
        items = [
            {
                "title": "Bad parent",
                "artifact_type": "prompt",
                "content": "x",
                "parent_id": FAKE_UUID,
            },
        ]
        resp = client.post("/api/artifacts/batch", json={"items": items})
        assert resp.status_code == 400
        assert "Batch item 0" in resp.json()["detail"]
        assert "Parent artifact not found" in resp.json()["detail"]

    def test_partial_failure_rolls_back(self, client):
        items = [
            {"title": "Good", "artifact_type": "prompt", "content": "ok"},
            {"title": "Bad", "artifact_type": "prompt", "content": "x", "parent_id": FAKE_UUID},
        ]
        client.post("/api/artifacts/batch", json={"items": items})
        resp = client.get("/api/artifacts")
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Batch Create — Protocols
# ---------------------------------------------------------------------------


class TestBatchCreateProtocols:
    def test_happy_path(self, client):
        items = [{"name": f"Proto {i}"} for i in range(3)]
        resp = client.post("/api/protocols/batch", json={"items": items})
        assert resp.status_code == 201
        assert resp.json()["count"] == 3

    def test_empty_batch(self, client):
        resp = client.post("/api/protocols/batch", json={"items": []})
        assert resp.status_code == 201
        assert resp.json() == {"created": [], "count": 0}

    def test_duplicate_name_in_batch(self, client):
        items = [{"name": "Same"}, {"name": "Same"}]
        resp = client.post("/api/protocols/batch", json={"items": items})
        assert resp.status_code == 400
        assert "Batch item 1" in resp.json()["detail"]
        assert "already exists" in resp.json()["detail"]

    def test_duplicate_name_existing(self, client):
        make_protocol(client, name="Existing")
        items = [{"name": "Existing"}]
        resp = client.post("/api/protocols/batch", json={"items": items})
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    def test_with_steps(self, client):
        items = [
            {
                "name": "Stepped",
                "steps": [{"order": 1, "title": "Step 1", "instruction": "Do it"}],
            },
        ]
        resp = client.post("/api/protocols/batch", json={"items": items})
        assert resp.status_code == 201
        assert resp.json()["created"][0]["steps"][0]["title"] == "Step 1"

    def test_with_tag_ids(self, client):
        tag = make_tag(client, name="proto-tag")
        items = [{"name": "Tagged proto", "tag_ids": [tag["id"]]}]
        resp = client.post("/api/protocols/batch", json={"items": items})
        assert resp.status_code == 201
        assert resp.json()["created"][0]["tags"][0]["name"] == "proto-tag"

    def test_partial_failure_rolls_back(self, client):
        items = [
            {"name": "Should not persist"},
            {"name": "Bad", "artifact_id": FAKE_UUID},
        ]
        client.post("/api/protocols/batch", json={"items": items})
        resp = client.get("/api/protocols")
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Batch Create — Directives
# ---------------------------------------------------------------------------


class TestBatchCreateDirectives:
    def test_happy_path(self, client):
        items = [
            {"name": f"Dir {i}", "content": f"Content {i}", "scope": "global"}
            for i in range(3)
        ]
        resp = client.post("/api/directives/batch", json={"items": items})
        assert resp.status_code == 201
        assert resp.json()["count"] == 3

    def test_empty_batch(self, client):
        resp = client.post("/api/directives/batch", json={"items": []})
        assert resp.status_code == 201
        assert resp.json() == {"created": [], "count": 0}

    def test_with_tag_ids(self, client):
        tag = make_tag(client, name="dir-tag")
        items = [
            {
                "name": "Tagged dir",
                "content": "Test",
                "scope": "global",
                "tag_ids": [tag["id"]],
            },
        ]
        resp = client.post("/api/directives/batch", json={"items": items})
        assert resp.status_code == 201
        assert resp.json()["created"][0]["tags"][0]["name"] == "dir-tag"

    def test_scope_validation(self, client):
        """Pydantic scope/scope_ref validation runs per item."""
        items = [
            {"name": "Bad scoped", "content": "x", "scope": "skill"},
        ]
        resp = client.post("/api/directives/batch", json={"items": items})
        assert resp.status_code == 422

    def test_partial_failure_tag_rolls_back(self, client):
        items = [
            {"name": "Good", "content": "ok", "scope": "global"},
            {
                "name": "Bad tags",
                "content": "ok",
                "scope": "global",
                "tag_ids": [FAKE_UUID],
            },
        ]
        client.post("/api/directives/batch", json={"items": items})
        resp = client.get("/api/directives")
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Batch Create — Skills
# ---------------------------------------------------------------------------


class TestBatchCreateSkills:
    def test_happy_path(self, client):
        items = [{"name": f"Skill {i}"} for i in range(3)]
        resp = client.post("/api/skills/batch", json={"items": items})
        assert resp.status_code == 201
        assert resp.json()["count"] == 3

    def test_empty_batch(self, client):
        resp = client.post("/api/skills/batch", json={"items": []})
        assert resp.status_code == 201
        assert resp.json() == {"created": [], "count": 0}

    def test_duplicate_name_in_batch(self, client):
        items = [{"name": "Same Skill"}, {"name": "Same Skill"}]
        resp = client.post("/api/skills/batch", json={"items": items})
        assert resp.status_code == 400
        assert "Batch item 1" in resp.json()["detail"]
        assert "already exists" in resp.json()["detail"]

    def test_multiple_defaults_in_batch(self, client):
        items = [
            {"name": "Default 1", "is_default": True},
            {"name": "Default 2", "is_default": True},
        ]
        resp = client.post("/api/skills/batch", json={"items": items})
        assert resp.status_code == 400
        assert "Batch item 1" in resp.json()["detail"]
        assert "default" in resp.json()["detail"].lower()

    def test_with_domain_ids(self, client):
        domain = make_domain(client, name="Skill domain")
        items = [{"name": "Linked skill", "domain_ids": [domain["id"]]}]
        resp = client.post("/api/skills/batch", json={"items": items})
        assert resp.status_code == 201
        assert resp.json()["created"][0]["domains"][0]["id"] == domain["id"]

    def test_fk_validation_artifact(self, client):
        items = [{"name": "Bad art", "artifact_id": FAKE_UUID}]
        resp = client.post("/api/skills/batch", json={"items": items})
        assert resp.status_code == 400
        assert "Artifact not found" in resp.json()["detail"]

    def test_partial_failure_rolls_back(self, client):
        items = [
            {"name": "Should not persist"},
            {"name": "Bad skill", "artifact_id": FAKE_UUID},
        ]
        client.post("/api/skills/batch", json={"items": items})
        resp = client.get("/api/skills")
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Batch Tag Attachment — Tasks
# ---------------------------------------------------------------------------


class TestBatchTagAttachTasks:
    def test_happy_path(self, client):
        task = make_task(client)
        t1 = make_tag(client, name="tag-a")
        t2 = make_tag(client, name="tag-b")

        resp = client.post(
            f"/api/tasks/{task['id']}/tags/batch",
            json={"tag_ids": [t1["id"], t2["id"]]},
        )
        assert resp.status_code == 200
        tag_names = {t["name"] for t in resp.json()}
        assert tag_names == {"tag-a", "tag-b"}

    def test_entity_not_found(self, client):
        resp = client.post(
            f"/api/tasks/{FAKE_UUID}/tags/batch",
            json={"tag_ids": [FAKE_UUID]},
        )
        assert resp.status_code == 404

    def test_tag_not_found(self, client):
        task = make_task(client)
        resp = client.post(
            f"/api/tasks/{task['id']}/tags/batch",
            json={"tag_ids": [FAKE_UUID]},
        )
        assert resp.status_code == 400
        assert FAKE_UUID in resp.json()["detail"]

    def test_idempotent(self, client):
        task = make_task(client)
        tag = make_tag(client, name="idem-tag")

        # Attach once
        client.post(
            f"/api/tasks/{task['id']}/tags/batch",
            json={"tag_ids": [tag["id"]]},
        )
        # Attach same again — should succeed without duplicating
        resp = client.post(
            f"/api/tasks/{task['id']}/tags/batch",
            json={"tag_ids": [tag["id"]]},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_returns_full_tag_list(self, client):
        task = make_task(client)
        t1 = make_tag(client, name="existing-tag")
        t2 = make_tag(client, name="new-tag")

        # Attach first tag individually
        client.post(f"/api/tasks/{task['id']}/tags/{t1['id']}")

        # Batch attach second tag
        resp = client.post(
            f"/api/tasks/{task['id']}/tags/batch",
            json={"tag_ids": [t2["id"]]},
        )
        assert resp.status_code == 200
        tag_names = {t["name"] for t in resp.json()}
        assert tag_names == {"existing-tag", "new-tag"}

    def test_max_size_exceeded(self, client):
        task = make_task(client)
        tag_ids = [str(uuid.uuid4()) for _ in range(101)]
        resp = client.post(
            f"/api/tasks/{task['id']}/tags/batch",
            json={"tag_ids": tag_ids},
        )
        assert resp.status_code == 422

    def test_empty_tag_ids(self, client):
        task = make_task(client)
        resp = client.post(
            f"/api/tasks/{task['id']}/tags/batch",
            json={"tag_ids": []},
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Batch Tag Attachment — Activity Logs
# ---------------------------------------------------------------------------


class TestBatchTagAttachActivity:
    def test_happy_path(self, client):
        entry = make_activity(client)
        t1 = make_tag(client, name="act-tag-1")
        t2 = make_tag(client, name="act-tag-2")

        resp = client.post(
            f"/api/activity/{entry['id']}/tags/batch",
            json={"tag_ids": [t1["id"], t2["id"]]},
        )
        assert resp.status_code == 200
        tag_names = {t["name"] for t in resp.json()}
        assert tag_names == {"act-tag-1", "act-tag-2"}

    def test_entity_not_found(self, client):
        resp = client.post(
            f"/api/activity/{FAKE_UUID}/tags/batch",
            json={"tag_ids": [FAKE_UUID]},
        )
        assert resp.status_code == 404

    def test_tag_not_found(self, client):
        entry = make_activity(client)
        resp = client.post(
            f"/api/activity/{entry['id']}/tags/batch",
            json={"tag_ids": [FAKE_UUID]},
        )
        assert resp.status_code == 400

    def test_idempotent(self, client):
        entry = make_activity(client)
        tag = make_tag(client, name="act-idem")

        client.post(
            f"/api/activity/{entry['id']}/tags/batch",
            json={"tag_ids": [tag["id"]]},
        )
        resp = client.post(
            f"/api/activity/{entry['id']}/tags/batch",
            json={"tag_ids": [tag["id"]]},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# Batch Tag Attachment — Artifacts
# ---------------------------------------------------------------------------


class TestBatchTagAttachArtifacts:
    def test_happy_path(self, client):
        artifact = make_artifact(client)
        t1 = make_tag(client, name="art-tag-1")
        t2 = make_tag(client, name="art-tag-2")

        resp = client.post(
            f"/api/artifacts/{artifact['id']}/tags/batch",
            json={"tag_ids": [t1["id"], t2["id"]]},
        )
        assert resp.status_code == 200
        tag_names = {t["name"] for t in resp.json()}
        assert tag_names == {"art-tag-1", "art-tag-2"}

    def test_entity_not_found(self, client):
        resp = client.post(
            f"/api/artifacts/{FAKE_UUID}/tags/batch",
            json={"tag_ids": [FAKE_UUID]},
        )
        assert resp.status_code == 404

    def test_tag_not_found(self, client):
        artifact = make_artifact(client)
        resp = client.post(
            f"/api/artifacts/{artifact['id']}/tags/batch",
            json={"tag_ids": [FAKE_UUID]},
        )
        assert resp.status_code == 400

    def test_idempotent(self, client):
        artifact = make_artifact(client)
        tag = make_tag(client, name="art-idem")

        client.post(
            f"/api/artifacts/{artifact['id']}/tags/batch",
            json={"tag_ids": [tag["id"]]},
        )
        resp = client.post(
            f"/api/artifacts/{artifact['id']}/tags/batch",
            json={"tag_ids": [tag["id"]]},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_returns_full_tag_list(self, client):
        artifact = make_artifact(client)
        t1 = make_tag(client, name="pre-existing")
        t2 = make_tag(client, name="batch-new")

        # Attach first tag individually
        client.post(f"/api/artifacts/{artifact['id']}/tags/{t1['id']}")

        # Batch attach second tag
        resp = client.post(
            f"/api/artifacts/{artifact['id']}/tags/batch",
            json={"tag_ids": [t2["id"]]},
        )
        assert resp.status_code == 200
        tag_names = {t["name"] for t in resp.json()}
        assert tag_names == {"pre-existing", "batch-new"}
