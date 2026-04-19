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

"""Tests for graduation API endpoints ([2G-06])."""

import uuid
from datetime import UTC, date, datetime, timedelta

from app.models import Domain, Habit, HabitCompletion, NotificationQueue, Routine  # noqa: I001
from tests.conftest import FAKE_UUID

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_habit(db, **overrides) -> Habit:
    """Insert a Habit directly via ORM."""
    nullable_grad_fields = ("graduation_window", "graduation_target", "graduation_threshold")
    force_null = {k for k in nullable_grad_fields if k in overrides and overrides[k] is None}
    constructor_overrides = {k: v for k, v in overrides.items() if k not in force_null}

    defaults = {
        "id": uuid.uuid4(),
        "title": "Test Habit",
        "status": "active",
        "frequency": "daily",
        "notification_frequency": "daily",
        "scaffolding_status": "accountable",
        "accountable_since": date.today() - timedelta(days=60),
    }
    defaults.update(constructor_overrides)
    habit = Habit(**defaults)
    db.add(habit)
    db.commit()

    if force_null:
        for field in force_null:
            setattr(habit, field, None)
        db.commit()

    db.refresh(habit)
    return habit


def _create_notification(db, habit_id, response, status, days_ago=5):
    """Insert a notification_queue entry for a habit."""
    n = NotificationQueue(
        id=uuid.uuid4(),
        notification_type="habit_nudge",
        delivery_type="notification",
        status=status,
        scheduled_at=datetime.now(tz=UTC) - timedelta(days=days_ago),
        target_entity_type="habit",
        target_entity_id=habit_id,
        message="Time for your habit!",
        response=response,
        scheduled_by="system",
    )
    db.add(n)
    db.commit()
    return n


def _create_routine(db) -> Routine:
    """Insert a Domain + Routine and return the Routine."""
    domain = Domain(id=uuid.uuid4(), name="Test Domain")
    db.add(domain)
    db.commit()
    routine = Routine(
        id=uuid.uuid4(),
        domain_id=domain.id,
        title="Test Routine",
        frequency="daily",
    )
    db.add(routine)
    db.commit()
    return routine


def _create_completion(db, habit_id, days_ago=0):
    """Insert a habit completion record."""
    c = HabitCompletion(
        id=uuid.uuid4(),
        habit_id=habit_id,
        completed_at=date.today() - timedelta(days=days_ago),
        source="individual",
    )
    db.add(c)
    db.commit()
    return c


def _eligible_habit(db, **overrides) -> Habit:
    """Create a habit that meets graduation criteria."""
    defaults = {
        "accountable_since": date.today() - timedelta(days=60),
        "scaffolding_status": "accountable",
        "notification_frequency": "daily",
        "status": "active",
    }
    defaults.update(overrides)
    habit = _create_habit(db, **defaults)
    for i in range(9):
        _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
    _create_notification(db, habit.id, "Skip today", "responded", days_ago=10)
    return habit


# ===========================================================================
# 1. POST /api/habits/{habit_id}/evaluate-graduation
# ===========================================================================


class TestEvaluateGraduationEndpoint:

    def test_happy_path(self, client, db):
        """Eligible accountable habit returns GraduationResult with eligible=True."""
        habit = _eligible_habit(db)
        resp = client.post(f"/api/habits/{habit.id}/evaluate-graduation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligible"] is True
        assert data["habit_id"] == str(habit.id)
        assert data["meets_rate"] is True
        assert data["meets_threshold"] is True

    def test_not_found(self, client):
        """Nonexistent habit returns 404."""
        resp = client.post(f"/api/habits/{FAKE_UUID}/evaluate-graduation")
        assert resp.status_code == 404

    def test_wrong_scaffolding_status(self, client, db):
        """Habit with scaffolding_status != accountable returns 422."""
        habit = _create_habit(db, scaffolding_status="tracking")
        resp = client.post(f"/api/habits/{habit.id}/evaluate-graduation")
        assert resp.status_code == 422
        assert "accountable" in resp.json()["detail"]

    def test_graduated_habit_rejected(self, client, db):
        """Already graduated habit returns 422."""
        habit = _create_habit(db, scaffolding_status="graduated",
                              notification_frequency="graduated")
        resp = client.post(f"/api/habits/{habit.id}/evaluate-graduation")
        assert resp.status_code == 422

    def test_paused_habit_rejected(self, client, db):
        """Paused habit returns 422 (wrong status)."""
        habit = _create_habit(db, status="paused", scaffolding_status="accountable")
        resp = client.post(f"/api/habits/{habit.id}/evaluate-graduation")
        assert resp.status_code == 422
        assert "active" in resp.json()["detail"]


# ===========================================================================
# 2. POST /api/habits/{habit_id}/graduate
# ===========================================================================


class TestGraduateEndpoint:

    def test_happy_path(self, client, db):
        """Eligible habit graduates successfully."""
        habit = _eligible_habit(db)
        resp = client.post(f"/api/habits/{habit.id}/graduate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "graduated successfully" in data["message"]

        db.refresh(habit)
        assert habit.scaffolding_status == "graduated"

    def test_force_graduation(self, client, db):
        """Force graduation bypasses eligibility check."""
        habit = _create_habit(db)  # No notifications — not eligible
        resp = client.post(
            f"/api/habits/{habit.id}/graduate", json={"force": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "(forced)" in data["message"]

    def test_ineligible_returns_422(self, client, db):
        """Ineligible habit without force returns 422."""
        habit = _create_habit(db)  # No notifications — not eligible
        resp = client.post(f"/api/habits/{habit.id}/graduate")
        assert resp.status_code == 422

    def test_already_graduated_409(self, client, db):
        """Already graduated habit returns 409."""
        habit = _create_habit(db, scaffolding_status="graduated",
                              notification_frequency="graduated")
        resp = client.post(f"/api/habits/{habit.id}/graduate")
        assert resp.status_code == 409
        assert "already graduated" in resp.json()["detail"]

    def test_not_found(self, client):
        """Nonexistent habit returns 404."""
        resp = client.post(f"/api/habits/{FAKE_UUID}/graduate")
        assert resp.status_code == 404

    def test_wrong_scaffolding_status_422(self, client, db):
        """Tracking habit returns 422."""
        habit = _create_habit(db, scaffolding_status="tracking")
        resp = client.post(f"/api/habits/{habit.id}/graduate")
        assert resp.status_code == 422

    def test_paused_status_422(self, client, db):
        """Paused habit returns 422."""
        habit = _create_habit(db, status="paused", scaffolding_status="accountable")
        resp = client.post(f"/api/habits/{habit.id}/graduate")
        assert resp.status_code == 422


# ===========================================================================
# 3. POST /api/habits/{habit_id}/evaluate-frequency
# ===========================================================================


class TestEvaluateFrequencyEndpoint:

    def test_happy_path(self, client, db):
        """Habit with high rate recommends step-down."""
        habit = _create_habit(db, notification_frequency="daily")
        for i in range(10):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)

        resp = client.post(f"/api/habits/{habit.id}/evaluate-frequency")
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommend_step_down"] is True
        assert data["recommended_frequency"] == "every_other_day"

    def test_not_found(self, client):
        """Nonexistent habit returns 404."""
        resp = client.post(f"/api/habits/{FAKE_UUID}/evaluate-frequency")
        assert resp.status_code == 404

    def test_no_recommendation(self, client, db):
        """Habit with low rate returns recommend_step_down=False."""
        habit = _create_habit(db, notification_frequency="daily")
        for i in range(10):
            _create_notification(db, habit.id, "Skip today", "responded", days_ago=i + 1)

        resp = client.post(f"/api/habits/{habit.id}/evaluate-frequency")
        assert resp.status_code == 200
        assert resp.json()["recommend_step_down"] is False


# ===========================================================================
# 4. POST /api/habits/{habit_id}/step-down-frequency
# ===========================================================================


class TestStepDownFrequencyEndpoint:

    def test_happy_path(self, client, db):
        """Step-down applies when recommended."""
        habit = _create_habit(db, notification_frequency="daily")
        for i in range(10):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)

        resp = client.post(f"/api/habits/{habit.id}/step-down-frequency")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["previous_frequency"] == "daily"
        assert data["new_frequency"] == "every_other_day"

        db.refresh(habit)
        assert habit.notification_frequency == "every_other_day"

    def test_not_recommended_422(self, client, db):
        """Step-down returns 422 when not recommended."""
        habit = _create_habit(db, notification_frequency="daily")
        for i in range(10):
            _create_notification(db, habit.id, "Skip today", "responded", days_ago=i + 1)

        resp = client.post(f"/api/habits/{habit.id}/step-down-frequency")
        assert resp.status_code == 422
        assert "not recommended" in resp.json()["detail"]["message"].lower()

    def test_not_found(self, client):
        """Nonexistent habit returns 404."""
        resp = client.post(f"/api/habits/{FAKE_UUID}/step-down-frequency")
        assert resp.status_code == 404


# ===========================================================================
# 5. POST /api/habits/{habit_id}/evaluate-slip
# ===========================================================================


class TestEvaluateSlipEndpoint:

    def test_happy_path_no_slip(self, client, db):
        """Graduated habit with recent completions shows no slip."""
        habit = _create_habit(
            db, scaffolding_status="graduated", notification_frequency="graduated",
        )
        for i in range(5):
            _create_completion(db, habit.id, days_ago=i + 1)

        resp = client.post(f"/api/habits/{habit.id}/evaluate-slip")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slip_detected"] is False
        assert data["recommendation"] == "no_action"

    def test_slip_detected(self, client, db):
        """Graduated habit with no completions shows critical slip."""
        habit = _create_habit(
            db, scaffolding_status="graduated", notification_frequency="graduated",
        )
        # No completions at all

        resp = client.post(f"/api/habits/{habit.id}/evaluate-slip")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slip_detected"] is True
        assert data["recommendation"] == "re_scaffold"

    def test_not_graduated_422(self, client, db):
        """Non-graduated habit returns 422."""
        habit = _create_habit(db, scaffolding_status="accountable")
        resp = client.post(f"/api/habits/{habit.id}/evaluate-slip")
        assert resp.status_code == 422
        assert "graduated" in resp.json()["detail"]

    def test_not_found(self, client):
        """Nonexistent habit returns 404."""
        resp = client.post(f"/api/habits/{FAKE_UUID}/evaluate-slip")
        assert resp.status_code == 404


# ===========================================================================
# 6. POST /api/habits/{habit_id}/re-scaffold
# ===========================================================================


class TestReScaffoldEndpoint:

    def test_happy_path(self, client, db):
        """Graduated habit is re-scaffolded to daily accountability."""
        habit = _create_habit(
            db, scaffolding_status="graduated", notification_frequency="graduated",
            friction_score=1, graduation_window=None, graduation_target=None,
            graduation_threshold=None,
        )
        resp = client.post(f"/api/habits/{habit.id}/re-scaffold")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["previous_scaffolding_status"] == "graduated"
        assert data["new_notification_frequency"] == "daily"
        assert data["re_scaffold_count"] == 1

        db.refresh(habit)
        assert habit.scaffolding_status == "accountable"
        assert habit.notification_frequency == "daily"

    def test_not_graduated_422(self, client, db):
        """Non-graduated habit returns 422."""
        habit = _create_habit(db, scaffolding_status="accountable")
        resp = client.post(f"/api/habits/{habit.id}/re-scaffold")
        assert resp.status_code == 422
        assert "graduated" in resp.json()["detail"]

    def test_not_found(self, client):
        """Nonexistent habit returns 404."""
        resp = client.post(f"/api/habits/{FAKE_UUID}/re-scaffold")
        assert resp.status_code == 404


# ===========================================================================
# 7. GET /api/habits/{habit_id}/graduation-status
# ===========================================================================


class TestGraduationStatusEndpoint:

    def test_happy_path_accountable(self, client, db):
        """Accountable habit returns composite graduation status."""
        habit = _eligible_habit(db, friction_score=3)
        resp = client.get(f"/api/habits/{habit.id}/graduation-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["habit_id"] == str(habit.id)
        assert data["scaffolding_status"] == "accountable"
        assert "graduation_params" in data
        assert "current_metrics" in data
        assert "progress_summary" in data
        assert "frequency_step_down" in data
        assert data["current_metrics"]["total_notifications"] > 0

    def test_graduated_habit_status(self, client, db):
        """Graduated habit returns appropriate progress summary."""
        habit = _create_habit(
            db, scaffolding_status="graduated", notification_frequency="graduated",
        )
        resp = client.get(f"/api/habits/{habit.id}/graduation-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scaffolding_status"] == "graduated"
        assert "graduated" in data["progress_summary"].lower()

    def test_tracking_habit_status(self, client, db):
        """Tracking habit returns appropriate progress summary."""
        habit = _create_habit(db, scaffolding_status="tracking")
        resp = client.get(f"/api/habits/{habit.id}/graduation-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scaffolding_status"] == "tracking"
        assert "tracking" in data["progress_summary"].lower()

    def test_not_found(self, client):
        """Nonexistent habit returns 404."""
        resp = client.get(f"/api/habits/{FAKE_UUID}/graduation-status")
        assert resp.status_code == 404

    def test_includes_frequency_step_down(self, client, db):
        """Status response includes frequency step-down evaluation."""
        habit = _create_habit(db, notification_frequency="daily")
        for i in range(10):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)

        resp = client.get(f"/api/habits/{habit.id}/graduation-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["frequency_step_down"]["eligible"] is True
        assert data["frequency_step_down"]["recommended_frequency"] == "every_other_day"


# ===========================================================================
# 8. GET /api/graduation/suggest-next?routine_id={routine_id}
# ===========================================================================


class TestSuggestNextEndpoint:

    def test_happy_path(self, client, db):
        """Routine with stable habits returns a suggestion."""
        routine = _create_routine(db)
        # Stable accountable habit (weekly)
        _create_habit(
            db, routine_id=routine.id, scaffolding_status="accountable",
            title="Weekly Habit", notification_frequency="weekly",
        )
        # Tracking habit to suggest
        _create_habit(
            db, routine_id=routine.id, scaffolding_status="tracking",
            title="Next Habit",
        )

        resp = client.get(
            "/api/graduation/suggest-next", params={"routine_id": str(routine.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["suggested_next"] is not None
        assert data["suggested_next"]["habit_name"] == "Next Habit"

    def test_missing_routine_id_422(self, client):
        """Missing routine_id query param returns 422."""
        resp = client.get("/api/graduation/suggest-next")
        assert resp.status_code == 422

    def test_routine_not_found(self, client):
        """Nonexistent routine returns 404."""
        resp = client.get(
            "/api/graduation/suggest-next", params={"routine_id": FAKE_UUID},
        )
        assert resp.status_code == 404

    def test_freeform_routine(self, client, db):
        """Routine with no habits returns ready=True."""
        routine = _create_routine(db)
        resp = client.get(
            "/api/graduation/suggest-next", params={"routine_id": str(routine.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["suggested_next"] is None


# ===========================================================================
# 9. POST /api/graduation/evaluate-all-slips
# ===========================================================================


class TestEvaluateAllSlipsEndpoint:

    def test_happy_path_no_slips(self, client, db):
        """No graduated habits returns evaluated_count=0."""
        resp = client.post("/api/graduation/evaluate-all-slips")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evaluated_count"] == 0
        assert data["attention_needed"] == []

    def test_with_slipping_habit(self, client, db):
        """Graduated habit with no completions appears in attention_needed."""
        habit = _create_habit(
            db, scaffolding_status="graduated", notification_frequency="graduated",
            title="Slipping Habit",
        )

        resp = client.post("/api/graduation/evaluate-all-slips")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evaluated_count"] == 1
        assert len(data["attention_needed"]) == 1
        assert data["attention_needed"][0]["habit_id"] == str(habit.id)

    def test_healthy_graduated_not_in_attention(self, client, db):
        """Graduated habit with recent completions is NOT in attention_needed."""
        habit = _create_habit(
            db, scaffolding_status="graduated", notification_frequency="graduated",
        )
        for i in range(5):
            _create_completion(db, habit.id, days_ago=i + 1)

        resp = client.post("/api/graduation/evaluate-all-slips")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evaluated_count"] == 1
        assert data["attention_needed"] == []

    def test_mixed_graduated_habits(self, client, db):
        """Only slipping habits appear in attention_needed."""
        # Healthy graduated habit
        good = _create_habit(
            db, scaffolding_status="graduated", notification_frequency="graduated",
            title="Healthy",
        )
        for i in range(5):
            _create_completion(db, good.id, days_ago=i + 1)

        # Slipping graduated habit
        bad = _create_habit(
            db, scaffolding_status="graduated", notification_frequency="graduated",
            title="Slipping",
        )

        resp = client.post("/api/graduation/evaluate-all-slips")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evaluated_count"] == 2
        assert len(data["attention_needed"]) == 1
        assert data["attention_needed"][0]["habit_id"] == str(bad.id)


# ===========================================================================
# 10. Activity-log side effects — endpoint-layer coverage
#
# Service-layer tests in test_graduation.py already assert the activity-log
# writes for each Stream G transition. These tests close the endpoint-to-
# retrieval Layer Coverage blind spot (issue #180): drive the transition
# through its HTTP endpoint, then query GET /api/activity?habit_id={id}
# and assert the expected entry is returned.
# ===========================================================================


class TestActivityLogEndpointCoverage:

    def test_graduate_evaluated_writes_activity_log(self, client, db):
        """Evaluated graduation via endpoint is retrievable at GET /api/activity."""
        habit = _eligible_habit(db)
        resp = client.post(f"/api/habits/{habit.id}/graduate")
        assert resp.status_code == 200

        log_resp = client.get(f"/api/activity?habit_id={habit.id}")
        assert log_resp.status_code == 200
        entries = log_resp.json()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["action_type"] == "completed"
        assert entry["habit_id"] == str(habit.id)
        assert entry["notes"].startswith(f"Habit graduated: {habit.title}")
        assert "(forced)" not in entry["notes"]

    def test_graduate_forced_writes_activity_log(self, client, db):
        """Forced graduation via endpoint is retrievable with '(forced)' label."""
        habit = _create_habit(db)  # No notifications — not eligible
        resp = client.post(
            f"/api/habits/{habit.id}/graduate", json={"force": True},
        )
        assert resp.status_code == 200

        log_resp = client.get(f"/api/activity?habit_id={habit.id}")
        assert log_resp.status_code == 200
        entries = log_resp.json()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["action_type"] == "completed"
        assert entry["habit_id"] == str(habit.id)
        assert entry["notes"].startswith(f"Habit graduated (forced): {habit.title}")

    def test_step_down_frequency_writes_activity_log(self, client, db):
        """Step-down via endpoint is retrievable at GET /api/activity."""
        habit = _create_habit(db, notification_frequency="daily")
        for i in range(10):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)

        resp = client.post(f"/api/habits/{habit.id}/step-down-frequency")
        assert resp.status_code == 200

        log_resp = client.get(f"/api/activity?habit_id={habit.id}")
        assert log_resp.status_code == 200
        entries = log_resp.json()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["action_type"] == "completed"
        assert entry["habit_id"] == str(habit.id)
        assert entry["notes"].startswith(
            f"Notification frequency stepped down: {habit.title}",
        )
        assert "daily → every_other_day" in entry["notes"]

    def test_re_scaffold_writes_activity_log(self, client, db):
        """Re-scaffold via endpoint is retrievable with action_type=reflected."""
        habit = _create_habit(
            db, scaffolding_status="graduated", notification_frequency="graduated",
            friction_score=1, graduation_window=None, graduation_target=None,
            graduation_threshold=None,
        )
        resp = client.post(f"/api/habits/{habit.id}/re-scaffold")
        assert resp.status_code == 200

        log_resp = client.get(f"/api/activity?habit_id={habit.id}")
        assert log_resp.status_code == 200
        entries = log_resp.json()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["action_type"] == "reflected"
        assert entry["habit_id"] == str(habit.id)
        assert entry["notes"].startswith(f"Habit re-scaffolded: {habit.title}")
        assert "re-scaffold #1" in entry["notes"]
