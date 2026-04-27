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

"""Tests for GET /api/habits/{habit_id}/completions ([2C-26] Part A)."""

from datetime import date, timedelta

from tests.conftest import FAKE_UUID, make_habit


class TestListHabitCompletions:

    def test_returns_completions_newest_first(self, client):
        habit = make_habit(client)
        for offset in (3, 1, 5, 2):
            d = (date.today() - timedelta(days=offset)).isoformat()
            client.post(f"/api/habits/{habit['id']}/complete", json={"completed_date": d})

        resp = client.get(f"/api/habits/{habit['id']}/completions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 4
        dates = [row["completed_at"] for row in body]
        assert dates == sorted(dates, reverse=True)

    def test_response_shape(self, client):
        habit = make_habit(client)
        client.post(f"/api/habits/{habit['id']}/complete", json={"notes": "felt good"})

        resp = client.get(f"/api/habits/{habit['id']}/completions")
        body = resp.json()
        assert len(body) == 1
        row = body[0]
        assert set(row.keys()) == {
            "id", "habit_id", "completed_at", "source", "notes", "created_at",
        }
        assert row["habit_id"] == habit["id"]
        assert row["source"] == "individual"
        assert row["notes"] == "felt good"

    def test_default_limit_is_20(self, client):
        habit = make_habit(client)
        for offset in range(25):
            d = (date.today() - timedelta(days=offset)).isoformat()
            client.post(f"/api/habits/{habit['id']}/complete", json={"completed_date": d})

        resp = client.get(f"/api/habits/{habit['id']}/completions")
        assert len(resp.json()) == 20

    def test_explicit_limit(self, client):
        habit = make_habit(client)
        for offset in range(10):
            d = (date.today() - timedelta(days=offset)).isoformat()
            client.post(f"/api/habits/{habit['id']}/complete", json={"completed_date": d})

        resp = client.get(f"/api/habits/{habit['id']}/completions?limit=3")
        assert len(resp.json()) == 3

    def test_limit_max_100(self, client):
        habit = make_habit(client)
        resp = client.get(f"/api/habits/{habit['id']}/completions?limit=101")
        assert resp.status_code == 422

    def test_limit_min_1(self, client):
        habit = make_habit(client)
        resp = client.get(f"/api/habits/{habit['id']}/completions?limit=0")
        assert resp.status_code == 422

    def test_completed_after_filter(self, client):
        habit = make_habit(client)
        for offset in (5, 3, 1):
            d = (date.today() - timedelta(days=offset)).isoformat()
            client.post(f"/api/habits/{habit['id']}/complete", json={"completed_date": d})

        cutoff = (date.today() - timedelta(days=3)).isoformat()
        resp = client.get(
            f"/api/habits/{habit['id']}/completions?completed_after={cutoff}"
        )
        body = resp.json()
        # Strictly after cutoff: only the offset=1 completion qualifies.
        assert len(body) == 1
        assert body[0]["completed_at"] == (date.today() - timedelta(days=1)).isoformat()

    def test_empty_when_no_completions(self, client):
        habit = make_habit(client)
        resp = client.get(f"/api/habits/{habit['id']}/completions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_404_when_habit_missing(self, client):
        resp = client.get(f"/api/habits/{FAKE_UUID}/completions")
        assert resp.status_code == 404

    def test_only_returns_target_habits_completions(self, client):
        h1 = make_habit(client, title="H1")
        h2 = make_habit(client, title="H2")
        client.post(f"/api/habits/{h1['id']}/complete")
        client.post(f"/api/habits/{h2['id']}/complete")

        resp = client.get(f"/api/habits/{h1['id']}/completions")
        body = resp.json()
        assert len(body) == 1
        assert body[0]["habit_id"] == h1["id"]
