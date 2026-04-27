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

"""Tests for GET /api/routines/{routine_id}/completions ([2C-26] Part B)."""

from datetime import date, timedelta

from tests.conftest import FAKE_UUID, make_domain, make_habit, make_routine


def _scripted_routine(client):
    """Routine with one child habit so completions create RoutineCompletion rows."""
    domain = make_domain(client)
    routine = make_routine(client, domain["id"])
    make_habit(client, routine_id=routine["id"], title="Child")
    return routine


class TestListRoutineCompletions:

    def test_returns_completions_newest_first(self, client):
        routine = _scripted_routine(client)
        for offset in (3, 1, 5, 2):
            d = (date.today() - timedelta(days=offset)).isoformat()
            client.post(
                f"/api/routines/{routine['id']}/complete",
                json={"completed_date": d, "status": "all_done"},
            )

        resp = client.get(f"/api/routines/{routine['id']}/completions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 4
        dates = [row["completed_at"] for row in body]
        assert dates == sorted(dates, reverse=True)

    def test_response_shape(self, client):
        routine = _scripted_routine(client)
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "partial", "freeform_note": "Only step 1"},
        )

        resp = client.get(f"/api/routines/{routine['id']}/completions")
        body = resp.json()
        assert len(body) == 1
        row = body[0]
        assert set(row.keys()) == {
            "id", "routine_id", "completed_at", "status",
            "freeform_note", "reconciled", "reconciled_at",
        }
        assert row["routine_id"] == routine["id"]
        assert row["status"] == "partial"
        assert row["freeform_note"] == "Only step 1"
        assert row["reconciled"] is False

    def test_default_limit_is_10(self, client):
        routine = _scripted_routine(client)
        for offset in range(15):
            d = (date.today() - timedelta(days=offset)).isoformat()
            client.post(
                f"/api/routines/{routine['id']}/complete",
                json={"completed_date": d, "status": "all_done"},
            )

        resp = client.get(f"/api/routines/{routine['id']}/completions")
        assert len(resp.json()) == 10

    def test_explicit_limit(self, client):
        routine = _scripted_routine(client)
        for offset in range(8):
            d = (date.today() - timedelta(days=offset)).isoformat()
            client.post(
                f"/api/routines/{routine['id']}/complete",
                json={"completed_date": d, "status": "all_done"},
            )

        resp = client.get(f"/api/routines/{routine['id']}/completions?limit=3")
        assert len(resp.json()) == 3

    def test_limit_max_100(self, client):
        routine = _scripted_routine(client)
        resp = client.get(f"/api/routines/{routine['id']}/completions?limit=101")
        assert resp.status_code == 422

    def test_limit_min_1(self, client):
        routine = _scripted_routine(client)
        resp = client.get(f"/api/routines/{routine['id']}/completions?limit=0")
        assert resp.status_code == 422

    def test_completed_after_filter(self, client):
        routine = _scripted_routine(client)
        for offset in (5, 3, 1):
            d = (date.today() - timedelta(days=offset)).isoformat()
            client.post(
                f"/api/routines/{routine['id']}/complete",
                json={"completed_date": d, "status": "all_done"},
            )

        cutoff = (date.today() - timedelta(days=3)).isoformat()
        resp = client.get(
            f"/api/routines/{routine['id']}/completions?completed_after={cutoff}"
        )
        body = resp.json()
        # Strictly after cutoff: only the offset=1 completion qualifies.
        assert len(body) == 1
        assert body[0]["completed_at"] == (date.today() - timedelta(days=1)).isoformat()

    def test_status_ascending_within_same_date(self, client):
        """Order spec: completed_at DESC, status ASC."""
        routine = _scripted_routine(client)
        # Two rows on the same date with different statuses
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "partial"},
        )
        client.post(
            f"/api/routines/{routine['id']}/complete",
            json={"status": "all_done"},
        )

        resp = client.get(f"/api/routines/{routine['id']}/completions")
        body = resp.json()
        assert len(body) == 2
        # Same date → ASC by status: 'all_done' < 'partial'
        assert body[0]["status"] == "all_done"
        assert body[1]["status"] == "partial"

    def test_empty_when_no_completions(self, client):
        routine = _scripted_routine(client)
        resp = client.get(f"/api/routines/{routine['id']}/completions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_404_when_routine_missing(self, client):
        resp = client.get(f"/api/routines/{FAKE_UUID}/completions")
        assert resp.status_code == 404

    def test_only_returns_target_routines_completions(self, client):
        r1 = _scripted_routine(client)
        r2 = _scripted_routine(client)
        client.post(f"/api/routines/{r1['id']}/complete")
        client.post(f"/api/routines/{r2['id']}/complete")

        resp = client.get(f"/api/routines/{r1['id']}/completions")
        body = resp.json()
        assert len(body) == 1
        assert body[0]["routine_id"] == r1["id"]
