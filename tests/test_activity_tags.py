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

"""Tests for activity-tag attachment, reverse lookup, tag filter, and tag-at-create."""

from tests.conftest import FAKE_UUID, make_activity, make_tag

# ---------------------------------------------------------------------------
# POST /api/activity/{activity_id}/tags/{tag_id}  — attach
# ---------------------------------------------------------------------------

class TestAttachTagToActivity:

    def test_attach_tag(self, client):
        tag = make_tag(client, name="session-handoff")
        entry = make_activity(client)
        resp = client.post(f"/api/activity/{entry['id']}/tags/{tag['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == tag["id"]

    def test_attach_idempotent(self, client):
        tag = make_tag(client, name="session-handoff")
        entry = make_activity(client)
        client.post(f"/api/activity/{entry['id']}/tags/{tag['id']}")
        resp = client.post(f"/api/activity/{entry['id']}/tags/{tag['id']}")
        assert resp.status_code == 200
        tags_resp = client.get(f"/api/activity/{entry['id']}/tags")
        assert len(tags_resp.json()) == 1

    def test_attach_invalid_activity(self, client):
        tag = make_tag(client, name="test")
        resp = client.post(f"/api/activity/{FAKE_UUID}/tags/{tag['id']}")
        assert resp.status_code == 404

    def test_attach_invalid_tag(self, client):
        entry = make_activity(client)
        resp = client.post(f"/api/activity/{entry['id']}/tags/{FAKE_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/activity/{activity_id}/tags/{tag_id}  — detach
# ---------------------------------------------------------------------------

class TestDetachTagFromActivity:

    def test_detach_tag(self, client):
        tag = make_tag(client, name="session-handoff")
        entry = make_activity(client)
        client.post(f"/api/activity/{entry['id']}/tags/{tag['id']}")
        resp = client.delete(f"/api/activity/{entry['id']}/tags/{tag['id']}")
        assert resp.status_code == 204

    def test_detach_invalid_activity(self, client):
        tag = make_tag(client, name="test")
        resp = client.delete(f"/api/activity/{FAKE_UUID}/tags/{tag['id']}")
        assert resp.status_code == 404

    def test_detach_invalid_tag(self, client):
        entry = make_activity(client)
        resp = client.delete(f"/api/activity/{entry['id']}/tags/{FAKE_UUID}")
        assert resp.status_code == 404

    def test_detach_not_attached(self, client):
        tag = make_tag(client, name="session-handoff")
        entry = make_activity(client)
        resp = client.delete(f"/api/activity/{entry['id']}/tags/{tag['id']}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/activity/{activity_id}/tags  — list tags on activity
# ---------------------------------------------------------------------------

class TestListActivityTags:

    def test_list_tags_on_activity(self, client):
        tag1 = make_tag(client, name="session-handoff")
        tag2 = make_tag(client, name="fluxnook")
        entry = make_activity(client)
        client.post(f"/api/activity/{entry['id']}/tags/{tag1['id']}")
        client.post(f"/api/activity/{entry['id']}/tags/{tag2['id']}")
        resp = client.get(f"/api/activity/{entry['id']}/tags")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_tags_empty(self, client):
        entry = make_activity(client)
        resp = client.get(f"/api/activity/{entry['id']}/tags")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_tags_invalid_activity(self, client):
        resp = client.get(f"/api/activity/{FAKE_UUID}/tags")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/tags/{tag_id}/activities  — reverse lookup
# ---------------------------------------------------------------------------

class TestReverseActivityLookup:

    def test_list_activities_for_tag(self, client):
        tag = make_tag(client, name="session-handoff")
        entry1 = make_activity(client)
        entry2 = make_activity(client, action_type="reflected")
        client.post(f"/api/activity/{entry1['id']}/tags/{tag['id']}")
        client.post(f"/api/activity/{entry2['id']}/tags/{tag['id']}")
        resp = client.get(f"/api/tags/{tag['id']}/activities")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_reverse_lookup_empty(self, client):
        tag = make_tag(client, name="unused")
        resp = client.get(f"/api/tags/{tag['id']}/activities")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_reverse_lookup_invalid_tag(self, client):
        resp = client.get(f"/api/tags/{FAKE_UUID}/activities")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/activity?tag=  — multi-tag AND filter
# ---------------------------------------------------------------------------

class TestActivityTagFilter:

    def test_filter_single_tag(self, client):
        tag = make_tag(client, name="session-handoff")
        entry1 = make_activity(client)
        make_activity(client, action_type="reflected")
        client.post(f"/api/activity/{entry1['id']}/tags/{tag['id']}")
        resp = client.get("/api/activity?tag=session-handoff")
        assert len(resp.json()) == 1
        assert resp.json()[0]["id"] == entry1["id"]

    def test_filter_multiple_tags_and_logic(self, client):
        tag1 = make_tag(client, name="movie")
        tag2 = make_tag(client, name="fluxnook")
        entry_both = make_activity(client, action_type="reflected")
        entry_one = make_activity(client, action_type="completed")
        client.post(f"/api/activity/{entry_both['id']}/tags/{tag1['id']}")
        client.post(f"/api/activity/{entry_both['id']}/tags/{tag2['id']}")
        client.post(f"/api/activity/{entry_one['id']}/tags/{tag1['id']}")

        resp = client.get("/api/activity?tag=movie,fluxnook")
        entries = resp.json()
        assert len(entries) == 1
        assert entries[0]["id"] == entry_both["id"]

    def test_filter_tag_case_insensitive(self, client):
        tag = make_tag(client, name="session-handoff")
        entry = make_activity(client)
        client.post(f"/api/activity/{entry['id']}/tags/{tag['id']}")
        resp = client.get("/api/activity?tag=session-handoff")
        assert len(resp.json()) == 1

    def test_filter_tag_no_matches(self, client):
        make_activity(client)
        resp = client.get("/api/activity?tag=nonexistent")
        assert resp.json() == []

    def test_filter_tag_composable_with_action_type(self, client):
        tag = make_tag(client, name="session-handoff")
        entry1 = make_activity(client, action_type="completed")
        entry2 = make_activity(client, action_type="reflected")
        client.post(f"/api/activity/{entry1['id']}/tags/{tag['id']}")
        client.post(f"/api/activity/{entry2['id']}/tags/{tag['id']}")
        resp = client.get("/api/activity?tag=session-handoff&action_type=reflected")
        entries = resp.json()
        assert len(entries) == 1
        assert entries[0]["id"] == entry2["id"]


# ---------------------------------------------------------------------------
# POST /api/activity with tag_ids  — tag at create
# ---------------------------------------------------------------------------

class TestTagAtCreate:

    def test_create_with_tag_ids(self, client):
        tag1 = make_tag(client, name="session-handoff")
        tag2 = make_tag(client, name="fluxnook")
        resp = client.post(
            "/api/activity",
            json={
                "action_type": "reflected",
                "tag_ids": [tag1["id"], tag2["id"]],
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["tags"]) == 2
        tag_names = {t["name"] for t in body["tags"]}
        assert tag_names == {"session-handoff", "fluxnook"}

    def test_create_with_empty_tag_ids(self, client):
        resp = client.post(
            "/api/activity",
            json={"action_type": "reflected", "tag_ids": []},
        )
        assert resp.status_code == 201
        assert resp.json()["tags"] == []

    def test_create_without_tag_ids(self, client):
        resp = client.post(
            "/api/activity",
            json={"action_type": "reflected"},
        )
        assert resp.status_code == 201
        assert resp.json()["tags"] == []

    def test_create_with_invalid_tag_id(self, client):
        resp = client.post(
            "/api/activity",
            json={
                "action_type": "reflected",
                "tag_ids": [FAKE_UUID],
            },
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tags in activity responses
# ---------------------------------------------------------------------------

class TestActivityResponseIncludesTags:

    def test_list_response_includes_tags(self, client):
        tag = make_tag(client, name="session-handoff")
        entry = make_activity(client)
        client.post(f"/api/activity/{entry['id']}/tags/{tag['id']}")
        resp = client.get("/api/activity")
        entries = resp.json()
        assert len(entries) == 1
        assert len(entries[0]["tags"]) == 1
        assert entries[0]["tags"][0]["name"] == "session-handoff"

    def test_detail_response_includes_tags(self, client):
        tag = make_tag(client, name="session-handoff")
        entry = make_activity(client)
        client.post(f"/api/activity/{entry['id']}/tags/{tag['id']}")
        resp = client.get(f"/api/activity/{entry['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["tags"]) == 1
        assert body["tags"][0]["name"] == "session-handoff"


# ---------------------------------------------------------------------------
# Cascade — deleting a tag removes activity associations
# ---------------------------------------------------------------------------

class TestActivityTagCascade:

    def test_delete_tag_cascades_activity_associations(self, client):
        tag = make_tag(client, name="temp")
        entry = make_activity(client)
        client.post(f"/api/activity/{entry['id']}/tags/{tag['id']}")
        client.delete(f"/api/tags/{tag['id']}")
        resp = client.get(f"/api/activity/{entry['id']}")
        assert resp.status_code == 200
        assert resp.json()["tags"] == []

    def test_delete_activity_cascades_tag_associations(self, client):
        tag = make_tag(client, name="persist")
        entry = make_activity(client)
        client.post(f"/api/activity/{entry['id']}/tags/{tag['id']}")
        client.delete(f"/api/activity/{entry['id']}")
        # Tag still exists
        resp = client.get(f"/api/tags/{tag['id']}")
        assert resp.status_code == 200
