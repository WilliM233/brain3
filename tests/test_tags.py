"""Tests for Tag CRUD and task-tag attachment endpoints."""

from tests.conftest import FAKE_UUID, make_tag, make_task

# ---------------------------------------------------------------------------
# POST /api/tags
# ---------------------------------------------------------------------------

class TestCreateTag:

    def test_create_tag(self, client):
        resp = client.post("/api/tags", json={"name": "Home-Depot"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "home-depot"
        assert "id" in body

    def test_create_tag_with_color(self, client):
        resp = client.post("/api/tags", json={"name": "urgent", "color": "#ff0000"})
        assert resp.status_code == 201
        assert resp.json()["color"] == "#ff0000"

    def test_get_or_create_returns_existing(self, client):
        first = client.post("/api/tags", json={"name": "errands"})
        assert first.status_code == 201
        second = client.post("/api/tags", json={"name": "errands"})
        assert second.status_code == 200
        assert second.json()["id"] == first.json()["id"]

    def test_get_or_create_case_insensitive(self, client):
        first = client.post("/api/tags", json={"name": "Home-Depot"})
        second = client.post("/api/tags", json={"name": "home-depot"})
        assert second.status_code == 200
        assert second.json()["id"] == first.json()["id"]

    def test_create_tag_missing_name(self, client):
        resp = client.post("/api/tags", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/tags
# ---------------------------------------------------------------------------

class TestListTags:

    def test_list_tags_empty(self, client):
        resp = client.get("/api/tags")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_tags(self, client):
        make_tag(client, name="alpha")
        make_tag(client, name="beta")
        resp = client.get("/api/tags")
        assert len(resp.json()) == 2

    def test_search_filter(self, client):
        make_tag(client, name="home-depot")
        make_tag(client, name="quick-win")
        resp = client.get("/api/tags?search=depot")
        tags = resp.json()
        assert len(tags) == 1
        assert tags[0]["name"] == "home-depot"

    def test_search_case_insensitive(self, client):
        make_tag(client, name="home-depot")
        resp = client.get("/api/tags?search=DEPOT")
        assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# GET /api/tags/{id}
# ---------------------------------------------------------------------------

class TestGetTag:

    def test_get_tag(self, client):
        tag = make_tag(client, name="errands")
        resp = client.get(f"/api/tags/{tag['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "errands"

    def test_get_tag_not_found(self, client):
        resp = client.get(f"/api/tags/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/tags/{id}
# ---------------------------------------------------------------------------

class TestUpdateTag:

    def test_patch_tag_name(self, client):
        tag = make_tag(client, name="old")
        resp = client.patch(f"/api/tags/{tag['id']}", json={"name": "New-Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "new-name"

    def test_patch_tag_color(self, client):
        tag = make_tag(client, name="errands")
        resp = client.patch(f"/api/tags/{tag['id']}", json={"color": "#00ff00"})
        assert resp.status_code == 200
        assert resp.json()["color"] == "#00ff00"
        assert resp.json()["name"] == "errands"

    def test_patch_tag_not_found(self, client):
        resp = client.patch(f"/api/tags/{FAKE_UUID}", json={"name": "x"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/tags/{id}
# ---------------------------------------------------------------------------

class TestDeleteTag:

    def test_delete_tag(self, client):
        tag = make_tag(client, name="doomed")
        resp = client.delete(f"/api/tags/{tag['id']}")
        assert resp.status_code == 204
        resp = client.get(f"/api/tags/{tag['id']}")
        assert resp.status_code == 404

    def test_delete_tag_not_found(self, client):
        resp = client.delete(f"/api/tags/{FAKE_UUID}")
        assert resp.status_code == 404

    def test_delete_tag_cascades_task_associations(self, client):
        tag = make_tag(client, name="temp")
        task = make_task(client, title="Tagged")
        client.post(f"/api/tasks/{task['id']}/tags/{tag['id']}")
        client.delete(f"/api/tags/{tag['id']}")
        # Task still exists, but tag is gone from its tags list
        resp = client.get(f"/api/tasks/{task['id']}")
        assert resp.status_code == 200
        assert resp.json()["tags"] == []


# ---------------------------------------------------------------------------
# POST /api/tasks/{task_id}/tags/{tag_id}  — attach
# ---------------------------------------------------------------------------

class TestAttachTag:

    def test_attach_tag(self, client):
        tag = make_tag(client, name="errands")
        task = make_task(client, title="Buy milk")
        resp = client.post(f"/api/tasks/{task['id']}/tags/{tag['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == tag["id"]

    def test_attach_idempotent(self, client):
        tag = make_tag(client, name="errands")
        task = make_task(client, title="Buy milk")
        client.post(f"/api/tasks/{task['id']}/tags/{tag['id']}")
        resp = client.post(f"/api/tasks/{task['id']}/tags/{tag['id']}")
        assert resp.status_code == 200
        # Still only one tag on the task
        tags_resp = client.get(f"/api/tasks/{task['id']}/tags")
        assert len(tags_resp.json()) == 1

    def test_attach_invalid_task(self, client):
        tag = make_tag(client, name="errands")
        resp = client.post(f"/api/tasks/{FAKE_UUID}/tags/{tag['id']}")
        assert resp.status_code == 404

    def test_attach_invalid_tag(self, client):
        task = make_task(client, title="Buy milk")
        resp = client.post(f"/api/tasks/{task['id']}/tags/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/tasks/{task_id}/tags/{tag_id}  — detach
# ---------------------------------------------------------------------------

class TestDetachTag:

    def test_detach_tag(self, client):
        tag = make_tag(client, name="errands")
        task = make_task(client, title="Buy milk")
        client.post(f"/api/tasks/{task['id']}/tags/{tag['id']}")
        resp = client.delete(f"/api/tasks/{task['id']}/tags/{tag['id']}")
        assert resp.status_code == 204

    def test_detach_invalid_task(self, client):
        tag = make_tag(client, name="errands")
        resp = client.delete(f"/api/tasks/{FAKE_UUID}/tags/{tag['id']}")
        assert resp.status_code == 404

    def test_detach_invalid_tag(self, client):
        task = make_task(client, title="Buy milk")
        resp = client.delete(f"/api/tasks/{task['id']}/tags/{FAKE_UUID}")
        assert resp.status_code == 404

    def test_detach_not_attached(self, client):
        tag = make_tag(client, name="errands")
        task = make_task(client, title="Buy milk")
        resp = client.delete(f"/api/tasks/{task['id']}/tags/{tag['id']}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/tasks/{task_id}/tags  — list tags on task
# ---------------------------------------------------------------------------

class TestListTaskTags:

    def test_list_tags_on_task(self, client):
        tag1 = make_tag(client, name="errands")
        tag2 = make_tag(client, name="quick-win")
        task = make_task(client, title="Buy milk")
        client.post(f"/api/tasks/{task['id']}/tags/{tag1['id']}")
        client.post(f"/api/tasks/{task['id']}/tags/{tag2['id']}")
        resp = client.get(f"/api/tasks/{task['id']}/tags")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_tags_empty(self, client):
        task = make_task(client, title="Buy milk")
        resp = client.get(f"/api/tasks/{task['id']}/tags")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_tags_invalid_task(self, client):
        resp = client.get(f"/api/tasks/{FAKE_UUID}/tags")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/tags/{tag_id}/tasks  — reverse lookup
# ---------------------------------------------------------------------------

class TestReverseLookup:

    def test_list_tasks_for_tag(self, client):
        tag = make_tag(client, name="home-depot")
        task1 = make_task(client, title="Buy lumber")
        task2 = make_task(client, title="Buy nails")
        client.post(f"/api/tasks/{task1['id']}/tags/{tag['id']}")
        client.post(f"/api/tasks/{task2['id']}/tags/{tag['id']}")
        resp = client.get(f"/api/tags/{tag['id']}/tasks")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_reverse_lookup_empty(self, client):
        tag = make_tag(client, name="unused")
        resp = client.get(f"/api/tags/{tag['id']}/tasks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_reverse_lookup_invalid_tag(self, client):
        resp = client.get(f"/api/tags/{FAKE_UUID}/tasks")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/tasks/{id} — TaskDetailResponse includes tags
# ---------------------------------------------------------------------------

class TestTaskDetailIncludesTags:

    def test_task_detail_shows_tags(self, client):
        tag = make_tag(client, name="errands")
        task = make_task(client, title="Buy milk")
        client.post(f"/api/tasks/{task['id']}/tags/{tag['id']}")
        resp = client.get(f"/api/tasks/{task['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["tags"]) == 1
        assert body["tags"][0]["name"] == "errands"
