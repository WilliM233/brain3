"""Tests for reporting and aggregation endpoints."""

import uuid as _uuid
from datetime import date, datetime, timedelta, timezone

from app.models import ActivityLog
from tests.conftest import make_domain, make_goal, make_project, make_routine, make_task

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_domain_hierarchy(client):
    """Create domain → goal → project → task chain and return all IDs."""
    domain = make_domain(client, name="Health")
    goal = make_goal(client, domain["id"], title="Exercise more")
    project = make_project(client, goal["id"], title="Gym plan")
    task = make_task(client, project_id=project["id"], title="Go to gym")
    return domain, goal, project, task


def _log_activity(db, **kwargs):
    """Insert an activity log entry directly via ORM."""
    # Convert string UUIDs to proper UUID objects for SQLite compatibility
    for key in ("task_id", "routine_id", "checkin_id"):
        if key in kwargs and isinstance(kwargs[key], str):
            kwargs[key] = _uuid.UUID(kwargs[key])
    entry = ActivityLog(**kwargs)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# GET /api/reports/activity-summary
# ---------------------------------------------------------------------------

class TestActivitySummary:

    def test_empty_range(self, client):
        resp = client.get(
            "/api/reports/activity-summary"
            "?after=2026-03-01T00:00:00&before=2026-03-07T23:59:59"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["entries_count"] == 0
        assert body["total_completed"] == 0
        assert body["total_skipped"] == 0
        assert body["total_deferred"] == 0
        assert body["total_duration_minutes"] == 0
        assert body["avg_energy_delta"] is None
        assert body["avg_mood"] is None

    def test_aggregations(self, client, db):
        _log_activity(
            db, action_type="completed", duration_minutes=30,
            energy_before=2, energy_after=4, mood_rating=4,
            logged_at=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
        )
        _log_activity(
            db, action_type="completed", duration_minutes=15,
            energy_before=3, energy_after=2, mood_rating=3,
            logged_at=datetime(2026, 3, 5, 14, 0, tzinfo=timezone.utc),
        )
        _log_activity(
            db, action_type="skipped",
            logged_at=datetime(2026, 3, 5, 16, 0, tzinfo=timezone.utc),
        )
        _log_activity(
            db, action_type="deferred",
            logged_at=datetime(2026, 3, 6, 10, 0, tzinfo=timezone.utc),
        )

        resp = client.get(
            "/api/reports/activity-summary"
            "?after=2026-03-01T00:00:00&before=2026-03-07T23:59:59"
        )
        body = resp.json()
        assert body["entries_count"] == 4
        assert body["total_completed"] == 2
        assert body["total_skipped"] == 1
        assert body["total_deferred"] == 1
        assert body["total_duration_minutes"] == 45
        # avg energy delta: (4-2 + 2-3) / 2 = (2 + -1) / 2 = 0.5
        assert body["avg_energy_delta"] == 0.5
        # avg mood: (4 + 3) / 2 = 3.5
        assert body["avg_mood"] == 3.5

    def test_date_range_exclusion(self, client, db):
        _log_activity(
            db, action_type="completed",
            logged_at=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
        )
        _log_activity(
            db, action_type="completed",
            logged_at=datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
        )
        resp = client.get(
            "/api/reports/activity-summary"
            "?after=2026-03-01T00:00:00&before=2026-03-31T23:59:59"
        )
        assert resp.json()["entries_count"] == 1


# ---------------------------------------------------------------------------
# GET /api/reports/domain-balance
# ---------------------------------------------------------------------------

class TestDomainBalance:

    def test_empty_domains(self, client):
        make_domain(client, name="Empty")
        resp = client.get("/api/reports/domain-balance")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["domain_name"] == "Empty"
        assert body[0]["active_goals"] == 0
        assert body[0]["active_projects"] == 0
        assert body[0]["pending_tasks"] == 0
        assert body[0]["overdue_tasks"] == 0
        assert body[0]["days_since_last_activity"] is None

    def test_counts(self, client):
        domain = make_domain(client, name="Health")
        goal = make_goal(client, domain["id"], title="Exercise")
        # paused goal shouldn't count
        make_goal(client, domain["id"], title="Paused", status="paused")
        project = make_project(client, goal["id"], title="Gym")
        # Activate the project
        client.patch(f"/api/projects/{project['id']}", json={"status": "active"})
        make_task(client, project_id=project["id"], title="Task 1")
        make_task(client, project_id=project["id"], title="Task 2")

        resp = client.get("/api/reports/domain-balance")
        body = resp.json()
        d = body[0]
        assert d["active_goals"] == 1
        assert d["active_projects"] == 1
        assert d["pending_tasks"] == 2

    def test_overdue_tasks(self, client):
        domain, goal, project, task = _setup_domain_hierarchy(client)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        make_task(
            client, project_id=project["id"], title="Overdue",
            due_date=yesterday, status="pending",
        )
        resp = client.get("/api/reports/domain-balance")
        assert resp.json()[0]["overdue_tasks"] == 1

    def test_days_since_activity(self, client, db):
        domain, goal, project, task = _setup_domain_hierarchy(client)
        _log_activity(
            db, task_id=task["id"], action_type="completed",
            logged_at=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
        )
        resp = client.get("/api/reports/domain-balance")
        d = resp.json()[0]
        assert d["days_since_last_activity"] is not None
        assert d["days_since_last_activity"] >= 0

    def test_days_since_routine_activity(self, client, db):
        domain = make_domain(client, name="Health")
        routine = make_routine(client, domain["id"], title="Walk")
        _log_activity(
            db, routine_id=routine["id"], action_type="completed",
            logged_at=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
        )
        resp = client.get("/api/reports/domain-balance")
        d = resp.json()[0]
        assert d["days_since_last_activity"] is not None


# ---------------------------------------------------------------------------
# GET /api/reports/routine-adherence
# ---------------------------------------------------------------------------

class TestRoutineAdherence:

    def test_empty(self, client):
        resp = client.get(
            "/api/reports/routine-adherence"
            "?after=2026-03-01T00:00:00&before=2026-03-07T23:59:59"
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_daily_routine(self, client, db):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"], title="Meditate", frequency="daily")
        # Log 5 completions in a 7-day period
        for day in range(1, 6):
            _log_activity(
                db, routine_id=routine["id"], action_type="completed",
                logged_at=datetime(2026, 3, day, 8, 0, tzinfo=timezone.utc),
            )
        resp = client.get(
            "/api/reports/routine-adherence"
            "?after=2026-03-01T00:00:00&before=2026-03-07T23:59:59"
        )
        body = resp.json()
        assert len(body) == 1
        r = body[0]
        assert r["routine_title"] == "Meditate"
        assert r["completions_in_period"] == 5
        assert r["expected_in_period"] == 7
        assert r["adherence_pct"] == 71.4

    def test_weekly_routine(self, client, db):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"], title="Review", frequency="weekly")
        _log_activity(
            db, routine_id=routine["id"], action_type="completed",
            logged_at=datetime(2026, 3, 3, 10, 0, tzinfo=timezone.utc),
        )
        # 14 days = 2 weeks expected
        resp = client.get(
            "/api/reports/routine-adherence"
            "?after=2026-03-01T00:00:00&before=2026-03-14T23:59:59"
        )
        r = resp.json()[0]
        assert r["expected_in_period"] == 2
        assert r["completions_in_period"] == 1
        assert r["adherence_pct"] == 50.0

    def test_adherence_capped_at_100(self, client, db):
        domain = make_domain(client)
        routine = make_routine(client, domain["id"], title="Walk", frequency="weekly")
        # Log 3 completions in a 7-day period (expected=1)
        for day in [1, 3, 5]:
            _log_activity(
                db, routine_id=routine["id"], action_type="completed",
                logged_at=datetime(2026, 3, day, 8, 0, tzinfo=timezone.utc),
            )
        resp = client.get(
            "/api/reports/routine-adherence"
            "?after=2026-03-01T00:00:00&before=2026-03-07T23:59:59"
        )
        assert resp.json()[0]["adherence_pct"] == 100.0

    def test_streak_is_broken(self, client):
        domain = make_domain(client)
        make_routine(client, domain["id"], title="Broken", frequency="daily")
        resp = client.get(
            "/api/reports/routine-adherence"
            "?after=2026-03-01T00:00:00&before=2026-03-07T23:59:59"
        )
        r = resp.json()[0]
        assert r["current_streak"] == 0
        assert r["streak_is_broken"] is True

    def test_weekday_expected(self, client, db):
        domain = make_domain(client)
        make_routine(client, domain["id"], title="Work", frequency="weekdays")
        # 2026-03-02 is Monday, 2026-03-08 is Sunday — 5 weekdays
        resp = client.get(
            "/api/reports/routine-adherence"
            "?after=2026-03-02T00:00:00&before=2026-03-08T23:59:59"
        )
        assert resp.json()[0]["expected_in_period"] == 5


# ---------------------------------------------------------------------------
# GET /api/reports/friction-analysis
# ---------------------------------------------------------------------------

class TestFrictionAnalysis:

    def test_empty(self, client):
        resp = client.get(
            "/api/reports/friction-analysis"
            "?after=2026-03-01T00:00:00&before=2026-03-31T23:59:59"
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_friction_grouping(self, client, db):
        # Create tasks with cognitive types
        t1 = make_task(
            client, title="Phone call",
            cognitive_type="communication", activation_friction=4, energy_cost=3,
        )
        t2 = make_task(
            client, title="Email",
            cognitive_type="communication", activation_friction=3, energy_cost=2,
        )
        t3 = make_task(
            client, title="Deep work",
            cognitive_type="focus_work", activation_friction=5, energy_cost=5,
        )

        # Log activities
        _log_activity(
            db, task_id=t1["id"], action_type="completed",
            friction_actual=2, energy_before=3, energy_after=2,
            logged_at=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
        )
        _log_activity(
            db, task_id=t2["id"], action_type="skipped",
            friction_actual=3,
            logged_at=datetime(2026, 3, 5, 14, 0, tzinfo=timezone.utc),
        )
        _log_activity(
            db, task_id=t3["id"], action_type="completed",
            friction_actual=3, energy_before=4, energy_after=1,
            logged_at=datetime(2026, 3, 5, 16, 0, tzinfo=timezone.utc),
        )

        resp = client.get(
            "/api/reports/friction-analysis"
            "?after=2026-03-01T00:00:00&before=2026-03-31T23:59:59"
        )
        body = resp.json()
        assert len(body) == 2

        comm = next(r for r in body if r["cognitive_type"] == "communication")
        assert comm["task_count"] == 2
        # avg predicted: (4+3)/2 = 3.5, avg actual: (2+3)/2 = 2.5
        assert comm["avg_predicted_friction"] == 3.5
        assert comm["avg_actual_friction"] == 2.5
        assert comm["friction_gap"] == 1.0  # overestimates
        assert comm["completion_rate"] == 50.0  # 1 completed, 1 skipped

        focus = next(r for r in body if r["cognitive_type"] == "focus_work")
        assert focus["task_count"] == 1
        assert focus["avg_energy_delta"] == -3.0  # 1 - 4

    def test_defaults_to_30_days(self, client, db):
        task = make_task(
            client, title="Recent",
            cognitive_type="errand", activation_friction=2, energy_cost=1,
        )
        _log_activity(
            db, task_id=task["id"], action_type="completed",
            friction_actual=1,
            logged_at=datetime.now(tz=timezone.utc) - timedelta(days=5),
        )
        resp = client.get("/api/reports/friction-analysis")
        assert len(resp.json()) == 1

    def test_excludes_no_cognitive_type(self, client, db):
        task = make_task(client, title="No type")
        _log_activity(
            db, task_id=task["id"], action_type="completed",
            friction_actual=1,
            logged_at=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
        )
        resp = client.get(
            "/api/reports/friction-analysis"
            "?after=2026-03-01T00:00:00&before=2026-03-31T23:59:59"
        )
        assert resp.json() == []
