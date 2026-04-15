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

"""Tests for graduation evaluation service, defaults resolution, and schema additions."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.models import ActivityLog, Habit, NotificationQueue
from app.services.graduation import (
    FrequencyChangeResult,
    FrequencyStepResult,
    GraduationExecutionResult,
    GraduationResult,
    apply_frequency_step_down,
    apply_re_scaffold_tightening,
    evaluate_frequency_step_down,
    evaluate_graduation,
    graduate_habit,
    next_step_down,
)
from app.services.graduation_defaults import resolve_graduation_params
from tests.conftest import make_habit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_habit(db, **overrides) -> Habit:
    """Insert a Habit directly via ORM.

    Fields with model-level defaults (graduation_window, graduation_target,
    graduation_threshold) need a two-phase approach when the caller wants
    them NULL — SQLAlchemy 2.0's column defaults override None at init time.
    """
    # Fields that have model-level Python defaults and need explicit nulling
    nullable_grad_fields = ("graduation_window", "graduation_target", "graduation_threshold")
    force_null = {k for k in nullable_grad_fields if k in overrides and overrides[k] is None}

    constructor_overrides = {
        k: v for k, v in overrides.items() if k not in force_null
    }

    defaults = {
        "id": uuid.uuid4(),
        "title": "Test Habit",
        "status": "active",
        "frequency": "daily",
        "notification_frequency": "daily",
        "scaffolding_status": "accountable",
        "introduced_at": date.today() - timedelta(days=60),
    }
    defaults.update(constructor_overrides)
    habit = Habit(**defaults)
    db.add(habit)
    db.commit()

    # Phase 2: force-null graduation fields via UPDATE
    if force_null:
        for field in force_null:
            setattr(habit, field, None)
        db.commit()

    db.refresh(habit)
    return habit


def _create_notification(db, habit_id: uuid.UUID, response: str | None,
                         status: str, days_ago: int = 5) -> NotificationQueue:
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


# ===========================================================================
# resolve_graduation_params
# ===========================================================================


class TestResolveGraduationParams:

    def test_all_defaults_friction_none(self, db):
        """Habit with no overrides and no friction_score gets middle-tier defaults."""
        habit = _create_habit(db, graduation_window=None, graduation_target=None,
                              graduation_threshold=None, friction_score=None)
        window, target, threshold = resolve_graduation_params(habit)
        assert (window, target, threshold) == (45, 0.85, 45)

    def test_friction_1_defaults(self, db):
        habit = _create_habit(db, friction_score=1, graduation_window=None,
                              graduation_target=None, graduation_threshold=None)
        window, target, threshold = resolve_graduation_params(habit)
        assert (window, target, threshold) == (30, 0.85, 30)

    def test_friction_5_defaults(self, db):
        habit = _create_habit(db, friction_score=5, graduation_window=None,
                              graduation_target=None, graduation_threshold=None)
        window, target, threshold = resolve_graduation_params(habit)
        assert (window, target, threshold) == (60, 0.80, 60)

    def test_per_habit_overrides(self, db):
        """Per-habit values take precedence over friction defaults."""
        habit = _create_habit(db, friction_score=1, graduation_window=90,
                              graduation_target=0.70, graduation_threshold=90)
        window, target, threshold = resolve_graduation_params(habit)
        assert window == 90
        assert target == 0.70
        assert threshold == 90

    def test_partial_override(self, db):
        """One override, rest from friction tier."""
        habit = _create_habit(db, friction_score=4, graduation_window=100,
                              graduation_target=None, graduation_threshold=None)
        window, target, threshold = resolve_graduation_params(habit)
        assert window == 100
        assert target == 0.80  # friction-4 default
        assert threshold == 60  # friction-4 default


# ===========================================================================
# apply_re_scaffold_tightening
# ===========================================================================


class TestReScaffoldTightening:

    def test_no_tightening(self):
        w, t, th = apply_re_scaffold_tightening(30, 0.85, 30, 0)
        assert (w, t, th) == (30, 0.85, 30)

    def test_single_re_scaffold(self):
        w, t, th = apply_re_scaffold_tightening(30, 0.85, 30, 1)
        assert w == 37   # int(30 * 1.25)
        assert t == 0.90  # 0.85 + 0.05
        assert th == 37  # int(30 * 1.25)

    def test_double_re_scaffold(self):
        w, t, th = apply_re_scaffold_tightening(30, 0.85, 30, 2)
        # First pass: 37, 0.90, 37
        # Second pass: int(37 * 1.25) = 46, min(0.95, 0.95) = 0.95, 46
        assert w == 46
        assert t == 0.95
        assert th == 46

    def test_target_caps_at_95(self):
        """Target never exceeds 0.95 even with many re-scaffolds."""
        w, t, th = apply_re_scaffold_tightening(30, 0.85, 30, 10)
        assert t == 0.95

    def test_friction_5_double_rescaffold(self):
        """Higher friction habits tighten more in absolute terms."""
        w, t, th = apply_re_scaffold_tightening(60, 0.80, 60, 2)
        # First: 75, 0.85, 75
        # Second: int(75 * 1.25) = 93, 0.90, 93
        assert w == 93
        assert t == pytest.approx(0.90)
        assert th == 93


# ===========================================================================
# evaluate_graduation
# ===========================================================================


class TestEvaluateGraduation:

    def test_eligible_habit(self, db):
        """Habit that meets both rate and threshold is eligible."""
        habit = _create_habit(db, introduced_at=date.today() - timedelta(days=60))
        # 10 notifications, 9 "Already done" = 90% rate
        for i in range(9):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        _create_notification(db, habit.id, "Skip today", "responded", days_ago=10)

        result = evaluate_graduation(db, habit.id)

        assert isinstance(result, GraduationResult)
        assert result.eligible is True
        assert result.meets_rate is True
        assert result.meets_threshold is True
        assert result.total_notifications == 10
        assert result.already_done_count == 9
        assert result.current_rate == 0.9
        assert result.blocking_reasons == []

    def test_ineligible_rate_too_low(self, db):
        """Habit with rate below target is not eligible."""
        habit = _create_habit(db, introduced_at=date.today() - timedelta(days=60))
        # 10 notifications, 5 "Already done" = 50%
        for i in range(5):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        for i in range(5):
            _create_notification(db, habit.id, "Skip today", "responded", days_ago=i + 6)

        result = evaluate_graduation(db, habit.id)

        assert result.eligible is False
        assert result.meets_rate is False
        assert result.meets_threshold is True
        assert any("below target" in r for r in result.blocking_reasons)

    def test_ineligible_not_enough_time(self, db):
        """Habit introduced recently (below threshold) is not eligible."""
        habit = _create_habit(db, introduced_at=date.today() - timedelta(days=10))
        for i in range(10):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)

        result = evaluate_graduation(db, habit.id)

        assert result.eligible is False
        assert result.meets_rate is True
        assert result.meets_threshold is False
        assert any("days since introduction" in r for r in result.blocking_reasons)

    def test_ineligible_no_notification_data(self, db):
        """Habit with no notifications in window is not eligible."""
        habit = _create_habit(db, introduced_at=date.today() - timedelta(days=60))

        result = evaluate_graduation(db, habit.id)

        assert result.eligible is False
        assert result.total_notifications == 0
        assert any("No notification data" in r for r in result.blocking_reasons)

    def test_wrong_scaffolding_status_tracking(self, db):
        """Habit in 'tracking' status cannot be evaluated."""
        habit = _create_habit(db, scaffolding_status="tracking")

        result = evaluate_graduation(db, habit.id)

        assert result.eligible is False
        assert any("accountable" in r for r in result.blocking_reasons)

    def test_wrong_scaffolding_status_graduated(self, db):
        """Already graduated habits cannot be re-evaluated."""
        habit = _create_habit(db, scaffolding_status="graduated")

        result = evaluate_graduation(db, habit.id)

        assert result.eligible is False
        assert any("accountable" in r for r in result.blocking_reasons)

    def test_re_scaffold_tightens_criteria(self, db):
        """Habit with re_scaffold_count > 0 has tightened criteria."""
        habit = _create_habit(
            db,
            introduced_at=date.today() - timedelta(days=60),
            re_scaffold_count=1,
            friction_score=1,
            graduation_window=None,
            graduation_target=None,
            graduation_threshold=None,
        )
        # Friction-1 defaults: (30, 0.85, 30) → tightened: (37, 0.90, 37)
        # 10 notifications, 9 "Already done" = 90% — exactly meets tightened target
        for i in range(9):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        _create_notification(db, habit.id, "Doing it now", "responded", days_ago=10)

        result = evaluate_graduation(db, habit.id)

        assert result.target_rate == 0.90
        assert result.window_days == 37
        assert result.threshold_days == 37
        assert result.eligible is True

    def test_re_scaffold_makes_previously_eligible_ineligible(self, db):
        """Same data that passes without re-scaffold fails with re_scaffold_count=1."""
        habit = _create_habit(
            db,
            introduced_at=date.today() - timedelta(days=60),
            re_scaffold_count=1,
            friction_score=1,
            graduation_window=None,
            graduation_target=None,
            graduation_threshold=None,
        )
        # 10 notifications, 8 "Already done" = 80% — would pass 0.85 normally...
        # but tightened target is 0.90
        for i in range(8):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        for i in range(2):
            _create_notification(db, habit.id, "Skip today", "responded", days_ago=i + 9)

        result = evaluate_graduation(db, habit.id)

        assert result.target_rate == 0.90
        assert result.eligible is False
        assert result.meets_rate is False

    def test_expired_notifications_counted(self, db):
        """Expired (unanswered) notifications are included in total count."""
        habit = _create_habit(db, introduced_at=date.today() - timedelta(days=60))
        for i in range(8):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        # 2 expired notifications (no response)
        for i in range(2):
            _create_notification(db, habit.id, None, "expired", days_ago=i + 9)

        result = evaluate_graduation(db, habit.id)

        assert result.total_notifications == 10
        assert result.already_done_count == 8
        assert result.current_rate == 0.8

    def test_pending_notifications_excluded(self, db):
        """Pending/delivered notifications are NOT included in evaluation."""
        habit = _create_habit(db, introduced_at=date.today() - timedelta(days=60))
        for i in range(10):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        # These should be excluded
        _create_notification(db, habit.id, None, "pending", days_ago=1)
        _create_notification(db, habit.id, None, "delivered", days_ago=1)

        result = evaluate_graduation(db, habit.id)

        assert result.total_notifications == 10  # only responded/expired

    def test_notifications_outside_window_excluded(self, db):
        """Notifications older than the window are not counted."""
        habit = _create_habit(
            db,
            introduced_at=date.today() - timedelta(days=120),
            friction_score=1,  # 30-day window
            graduation_window=None,
            graduation_target=None,
            graduation_threshold=None,
        )
        # 5 recent "Already done" (within 30-day window)
        for i in range(5):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        # 5 old ones (outside window)
        for i in range(5):
            _create_notification(db, habit.id, "Skip today", "responded", days_ago=35 + i)

        result = evaluate_graduation(db, habit.id)

        assert result.total_notifications == 5
        assert result.already_done_count == 5
        assert result.current_rate == 1.0

    def test_nonexistent_habit_raises(self, db):
        """Evaluating a nonexistent habit raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            evaluate_graduation(db, uuid.uuid4())

    def test_habit_with_no_introduced_at(self, db):
        """Habit with no introduced_at gets 0 days_since_introduction."""
        habit = _create_habit(db, introduced_at=None)
        for i in range(10):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)

        result = evaluate_graduation(db, habit.id)

        assert result.days_since_introduction == 0
        assert result.meets_threshold is False


# ===========================================================================
# Schema validation — friction_score on create/update
# ===========================================================================


class TestFrictionScoreValidation:

    def test_create_with_valid_friction_score(self, client):
        resp = client.post("/api/habits", json={
            "title": "Test", "frequency": "daily", "friction_score": 3,
        })
        assert resp.status_code == 201
        assert resp.json()["friction_score"] == 3

    def test_create_with_null_friction_score(self, client):
        resp = client.post("/api/habits", json={
            "title": "Test", "frequency": "daily",
        })
        assert resp.status_code == 201
        assert resp.json()["friction_score"] is None

    def test_create_friction_score_too_low(self, client):
        resp = client.post("/api/habits", json={
            "title": "Test", "frequency": "daily", "friction_score": 0,
        })
        assert resp.status_code == 422

    def test_create_friction_score_too_high(self, client):
        resp = client.post("/api/habits", json={
            "title": "Test", "frequency": "daily", "friction_score": 6,
        })
        assert resp.status_code == 422

    def test_update_friction_score(self, client):
        habit = make_habit(client)
        resp = client.patch(
            f"/api/habits/{habit['id']}", json={"friction_score": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["friction_score"] == 5

    def test_update_friction_score_invalid(self, client):
        habit = make_habit(client)
        resp = client.patch(
            f"/api/habits/{habit['id']}", json={"friction_score": 10},
        )
        assert resp.status_code == 422

    def test_response_includes_new_fields(self, client):
        """HabitResponse includes re_scaffold_count and last_frequency_changed_at."""
        habit = make_habit(client)
        assert habit["re_scaffold_count"] == 0
        assert habit["last_frequency_changed_at"] is None


# ===========================================================================
# graduate_habit — execution & state transition
# ===========================================================================


class TestGraduateHabit:
    """Tests for the graduate_habit() service function ([2G-02])."""

    def _eligible_habit(self, db, **overrides) -> Habit:
        """Create a habit that meets graduation criteria."""
        defaults = {
            "introduced_at": date.today() - timedelta(days=60),
            "scaffolding_status": "accountable",
            "notification_frequency": "daily",
            "status": "active",
        }
        defaults.update(overrides)
        habit = _create_habit(db, **defaults)
        # 10 notifications, 9 "Already done" = 90% rate
        for i in range(9):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        _create_notification(db, habit.id, "Skip today", "responded", days_ago=10)
        return habit

    def _ineligible_habit(self, db, **overrides) -> Habit:
        """Create a habit that does NOT meet graduation criteria (low rate)."""
        defaults = {
            "introduced_at": date.today() - timedelta(days=60),
            "scaffolding_status": "accountable",
            "notification_frequency": "daily",
            "status": "active",
        }
        defaults.update(overrides)
        habit = _create_habit(db, **defaults)
        # 10 notifications, 3 "Already done" = 30% rate
        for i in range(3):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        for i in range(7):
            _create_notification(db, habit.id, "Skip today", "responded", days_ago=i + 4)
        return habit

    # --- Successful graduation ---

    def test_successful_graduation(self, db):
        """Eligible habit transitions scaffolding_status and notification_frequency."""
        habit = self._eligible_habit(db)
        original_best_streak = habit.best_streak
        original_last_completed = habit.last_completed

        result = graduate_habit(db, habit.id)

        assert isinstance(result, GraduationExecutionResult)
        assert result.success is True
        assert result.previous_scaffolding_status == "accountable"
        assert result.previous_notification_frequency == "daily"
        assert result.evaluation is not None
        assert result.evaluation.eligible is True
        assert "graduated successfully" in result.message

        db.refresh(habit)
        assert habit.scaffolding_status == "graduated"
        assert habit.notification_frequency == "graduated"
        assert habit.status == "active"
        assert habit.best_streak == original_best_streak
        assert habit.last_completed == original_last_completed

    def test_graduation_preserves_active_status(self, db):
        """habit.status remains 'active' after graduation."""
        habit = self._eligible_habit(db)
        graduate_habit(db, habit.id)
        db.refresh(habit)
        assert habit.status == "active"

    def test_graduation_preserves_streak_history(self, db):
        """best_streak and last_completed are unchanged after graduation."""
        habit = self._eligible_habit(
            db, best_streak=15, last_completed=date.today() - timedelta(days=1),
        )
        # Force the values in since _create_habit defaults may not set them
        habit.best_streak = 15
        habit.last_completed = date.today() - timedelta(days=1)
        db.commit()
        db.refresh(habit)

        graduate_habit(db, habit.id)
        db.refresh(habit)

        assert habit.best_streak == 15
        assert habit.last_completed == date.today() - timedelta(days=1)

    # --- Forced graduation ---

    def test_forced_graduation_bypasses_eligibility(self, db):
        """force=True graduates even when evaluation says ineligible."""
        habit = self._ineligible_habit(db)

        result = graduate_habit(db, habit.id, force=True)

        assert result.success is True
        assert result.evaluation is not None
        assert result.evaluation.eligible is False
        assert "(forced)" in result.message

        db.refresh(habit)
        assert habit.scaffolding_status == "graduated"
        assert habit.notification_frequency == "graduated"

    def test_forced_graduation_activity_log_label(self, db):
        """Forced graduation activity log entry includes '(forced)' marker."""
        habit = self._ineligible_habit(db)
        graduate_habit(db, habit.id, force=True)

        log = (
            db.query(ActivityLog)
            .filter(ActivityLog.habit_id == habit.id)
            .first()
        )
        assert log is not None
        assert "(forced)" in log.notes

    # --- Ineligible habit (force=False) ---

    def test_ineligible_returns_failure(self, db):
        """Ineligible habit with force=False returns success=False."""
        habit = self._ineligible_habit(db)

        result = graduate_habit(db, habit.id, force=False)

        assert result.success is False
        assert result.evaluation is not None
        assert result.evaluation.eligible is False
        assert len(result.evaluation.blocking_reasons) > 0

        db.refresh(habit)
        assert habit.scaffolding_status == "accountable"
        assert habit.notification_frequency == "daily"

    # --- Wrong status ---

    def test_paused_habit_rejected(self, db):
        """Cannot graduate a paused habit."""
        habit = _create_habit(
            db, status="paused", scaffolding_status="accountable",
            notification_frequency="daily",
        )
        with pytest.raises(Exception) as exc_info:
            graduate_habit(db, habit.id)
        assert exc_info.value.status_code == 400
        assert "paused" in exc_info.value.detail

    def test_abandoned_habit_rejected(self, db):
        """Cannot graduate an abandoned habit."""
        habit = _create_habit(
            db, status="abandoned", scaffolding_status="accountable",
            notification_frequency="daily",
        )
        with pytest.raises(Exception) as exc_info:
            graduate_habit(db, habit.id)
        assert exc_info.value.status_code == 400
        assert "abandoned" in exc_info.value.detail

    # --- Wrong scaffolding_status ---

    def test_tracking_scaffolding_rejected(self, db):
        """Cannot graduate from 'tracking' scaffolding_status."""
        habit = _create_habit(
            db, scaffolding_status="tracking", notification_frequency="daily",
        )
        with pytest.raises(Exception) as exc_info:
            graduate_habit(db, habit.id)
        assert exc_info.value.status_code == 400
        assert "tracking" in exc_info.value.detail

    # --- Already graduated ---

    def test_already_graduated_returns_failure(self, db):
        """Already graduated habit returns success=False (not an exception)."""
        habit = _create_habit(
            db, scaffolding_status="graduated", notification_frequency="graduated",
        )

        result = graduate_habit(db, habit.id)

        assert result.success is False
        assert result.message == "Habit is already graduated"
        assert result.evaluation is None

    # --- Nonexistent habit ---

    def test_nonexistent_habit_404(self, db):
        """Nonexistent habit_id raises 404."""
        with pytest.raises(Exception) as exc_info:
            graduate_habit(db, uuid.uuid4())
        assert exc_info.value.status_code == 404

    # --- Activity log ---

    def test_activity_log_created_on_success(self, db):
        """Successful graduation creates an activity log entry."""
        habit = self._eligible_habit(db)
        graduate_habit(db, habit.id)

        log = (
            db.query(ActivityLog)
            .filter(ActivityLog.habit_id == habit.id)
            .first()
        )
        assert log is not None
        assert log.action_type == "completed"
        assert habit.title in log.notes
        assert "graduated" in log.notes.lower()
        assert "Rate:" in log.notes
        assert "Streak preserved" in log.notes

    def test_no_activity_log_on_failure(self, db):
        """Failed graduation does NOT create an activity log entry."""
        habit = self._ineligible_habit(db)
        graduate_habit(db, habit.id, force=False)

        log_count = (
            db.query(ActivityLog)
            .filter(ActivityLog.habit_id == habit.id)
            .count()
        )
        assert log_count == 0

    def test_evaluated_graduation_no_forced_label(self, db):
        """Normal (non-forced) graduation does NOT include '(forced)' in activity log."""
        habit = self._eligible_habit(db)
        graduate_habit(db, habit.id)

        log = (
            db.query(ActivityLog)
            .filter(ActivityLog.habit_id == habit.id)
            .first()
        )
        assert "(forced)" not in log.notes


# ===========================================================================
# [2G-03] next_step_down
# ===========================================================================


class TestNextStepDown:

    def test_daily_to_every_other_day(self):
        assert next_step_down("daily") == "every_other_day"

    def test_every_other_day_to_twice_week(self):
        assert next_step_down("every_other_day") == "twice_week"

    def test_twice_week_to_weekly(self):
        assert next_step_down("twice_week") == "weekly"

    def test_weekly_returns_none(self):
        assert next_step_down("weekly") is None

    def test_graduated_returns_none(self):
        assert next_step_down("graduated") is None

    def test_none_returns_none(self):
        assert next_step_down("none") is None

    def test_unknown_returns_none(self):
        assert next_step_down("bogus") is None


# ===========================================================================
# [2G-03] evaluate_frequency_step_down
# ===========================================================================


class TestEvaluateFrequencyStepDown:

    def _habit_with_notifications(
        self, db, *, notification_frequency="daily", already_done=10,
        other_response=4, status="active", scaffolding_status="accountable",
        last_frequency_changed_at=None, **habit_overrides,
    ) -> Habit:
        """Create a habit with a mix of notification responses."""
        habit = _create_habit(
            db,
            notification_frequency=notification_frequency,
            status=status,
            scaffolding_status=scaffolding_status,
            last_frequency_changed_at=last_frequency_changed_at,
            **habit_overrides,
        )
        for i in range(already_done):
            _create_notification(
                db, habit.id, "Already done", "responded", days_ago=i + 1,
            )
        for i in range(other_response):
            _create_notification(
                db, habit.id, "Skip today", "responded",
                days_ago=already_done + i + 1,
            )
        return habit

    # --- Recommends step-down ---

    def test_daily_step_down_recommended(self, db):
        """Daily habit with >= 60% already-done rate recommends every_other_day."""
        habit = self._habit_with_notifications(
            db, notification_frequency="daily", already_done=9, other_response=5,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert isinstance(result, FrequencyStepResult)
        assert result.recommend_step_down is True
        assert result.current_frequency == "daily"
        assert result.recommended_frequency == "every_other_day"
        assert result.current_rate == pytest.approx(9 / 14)
        assert result.notifications_evaluated == 14
        assert result.cooldown_active is False
        assert result.blocking_reasons == []

    def test_every_other_day_step_down(self, db):
        """every_other_day → twice_week when rate meets threshold."""
        habit = self._habit_with_notifications(
            db, notification_frequency="every_other_day",
            already_done=10, other_response=4,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is True
        assert result.recommended_frequency == "twice_week"

    def test_twice_week_step_down(self, db):
        """twice_week → weekly when rate meets threshold."""
        habit = self._habit_with_notifications(
            db, notification_frequency="twice_week",
            already_done=10, other_response=4,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is True
        assert result.recommended_frequency == "weekly"

    def test_exact_threshold_recommends(self, db):
        """Exactly 60% rate still recommends step-down."""
        # 6 out of 10 = 60%
        habit = self._habit_with_notifications(
            db, notification_frequency="daily",
            already_done=6, other_response=4,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is True
        assert result.current_rate == pytest.approx(0.6)

    # --- No recommendation ---

    def test_weekly_no_step_down(self, db):
        """Weekly habit cannot step down further — graduation is separate."""
        habit = self._habit_with_notifications(
            db, notification_frequency="weekly",
            already_done=14, other_response=0,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert result.recommended_frequency is None
        assert any("minimum stepped frequency" in r for r in result.blocking_reasons)

    def test_graduated_no_step_down(self, db):
        """Graduated frequency is not in the progression."""
        habit = self._habit_with_notifications(
            db, notification_frequency="graduated",
            already_done=10, other_response=4,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert any("not in the step-down progression" in r for r in result.blocking_reasons)

    def test_none_frequency_no_step_down(self, db):
        """'none' frequency is not in the progression."""
        habit = self._habit_with_notifications(
            db, notification_frequency="none",
            already_done=10, other_response=4,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False

    def test_rate_below_threshold(self, db):
        """Rate below 60% does not recommend step-down."""
        # 5 out of 14 = ~36%
        habit = self._habit_with_notifications(
            db, notification_frequency="daily",
            already_done=5, other_response=9,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert result.current_rate == pytest.approx(5 / 14)
        assert any("below step-down threshold" in r for r in result.blocking_reasons)

    def test_insufficient_notifications(self, db):
        """Fewer than 5 notifications returns no recommendation."""
        habit = self._habit_with_notifications(
            db, notification_frequency="daily",
            already_done=3, other_response=1,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert result.notifications_evaluated == 4
        assert any("Need at least 5" in r for r in result.blocking_reasons)

    def test_zero_notifications(self, db):
        """No notifications at all returns no recommendation."""
        habit = self._habit_with_notifications(
            db, notification_frequency="daily",
            already_done=0, other_response=0,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert result.notifications_evaluated == 0

    # --- Cooldown ---

    def test_cooldown_active(self, db):
        """Habit with recent frequency change is in cooldown."""
        recent = datetime.now(tz=UTC) - timedelta(days=3)
        habit = self._habit_with_notifications(
            db, notification_frequency="daily",
            already_done=14, other_response=0,
            last_frequency_changed_at=recent,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert result.cooldown_active is True
        assert result.cooldown_expires_at is not None
        assert any("Cooldown active" in r for r in result.blocking_reasons)

    def test_cooldown_expired(self, db):
        """Habit with frequency change > 7 days ago is past cooldown."""
        old = datetime.now(tz=UTC) - timedelta(days=10)
        habit = self._habit_with_notifications(
            db, notification_frequency="daily",
            already_done=14, other_response=0,
            last_frequency_changed_at=old,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is True
        assert result.cooldown_active is False

    def test_cooldown_exactly_7_days(self, db):
        """Frequency change exactly 7 days ago — cooldown has expired."""
        boundary = datetime.now(tz=UTC) - timedelta(days=7)
        habit = self._habit_with_notifications(
            db, notification_frequency="daily",
            already_done=14, other_response=0,
            last_frequency_changed_at=boundary,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is True
        assert result.cooldown_active is False

    # --- Status gates ---

    def test_paused_habit_rejected(self, db):
        """Paused habits are not evaluated for step-down."""
        habit = self._habit_with_notifications(
            db, notification_frequency="daily",
            already_done=14, other_response=0,
            status="paused",
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert any("active" in r for r in result.blocking_reasons)

    def test_tracking_scaffolding_rejected(self, db):
        """Tracking habits are not evaluated for step-down."""
        habit = self._habit_with_notifications(
            db, notification_frequency="daily",
            already_done=14, other_response=0,
            scaffolding_status="tracking",
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False

    def test_nonexistent_habit_raises(self, db):
        """Evaluating a nonexistent habit raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            evaluate_frequency_step_down(db, uuid.uuid4())

    # --- LIMIT-based query ---

    def test_only_most_recent_14_considered(self, db):
        """Only the 14 most recent notifications are evaluated."""
        habit = _create_habit(db, notification_frequency="daily")
        # 14 recent "Already done"
        for i in range(14):
            _create_notification(
                db, habit.id, "Already done", "responded", days_ago=i + 1,
            )
        # 10 older "Skip today" — should be excluded by LIMIT
        for i in range(10):
            _create_notification(
                db, habit.id, "Skip today", "responded", days_ago=20 + i,
            )

        result = evaluate_frequency_step_down(db, habit.id)

        assert result.notifications_evaluated == 14
        assert result.current_rate == 1.0
        assert result.recommend_step_down is True

    def test_pending_excluded(self, db):
        """Pending notifications are not counted."""
        habit = _create_habit(db, notification_frequency="daily")
        for i in range(10):
            _create_notification(
                db, habit.id, "Already done", "responded", days_ago=i + 1,
            )
        _create_notification(db, habit.id, None, "pending", days_ago=1)
        _create_notification(db, habit.id, None, "delivered", days_ago=1)

        result = evaluate_frequency_step_down(db, habit.id)

        assert result.notifications_evaluated == 10


# ===========================================================================
# [2G-03] apply_frequency_step_down
# ===========================================================================


class TestApplyFrequencyStepDown:

    def _accountable_habit(self, db, notification_frequency="daily") -> Habit:
        return _create_habit(
            db,
            notification_frequency=notification_frequency,
            scaffolding_status="accountable",
        )

    # --- Successful transitions ---

    def test_daily_to_every_other_day(self, db):
        habit = self._accountable_habit(db, "daily")
        result = apply_frequency_step_down(db, habit.id, "every_other_day")

        assert isinstance(result, FrequencyChangeResult)
        assert result.success is True
        assert result.previous_frequency == "daily"
        assert result.new_frequency == "every_other_day"

        db.refresh(habit)
        assert habit.notification_frequency == "every_other_day"
        assert habit.last_frequency_changed_at is not None

    def test_every_other_day_to_twice_week(self, db):
        habit = self._accountable_habit(db, "every_other_day")
        result = apply_frequency_step_down(db, habit.id, "twice_week")

        assert result.success is True
        db.refresh(habit)
        assert habit.notification_frequency == "twice_week"

    def test_twice_week_to_weekly(self, db):
        habit = self._accountable_habit(db, "twice_week")
        result = apply_frequency_step_down(db, habit.id, "weekly")

        assert result.success is True
        db.refresh(habit)
        assert habit.notification_frequency == "weekly"

    def test_activity_log_created(self, db):
        """Successful step-down creates an activity log entry."""
        habit = self._accountable_habit(db)
        apply_frequency_step_down(db, habit.id, "every_other_day")

        log = (
            db.query(ActivityLog)
            .filter(ActivityLog.habit_id == habit.id)
            .first()
        )
        assert log is not None
        assert log.action_type == "completed"
        assert "stepped down" in log.notes
        assert "daily" in log.notes
        assert "every_other_day" in log.notes

    def test_last_frequency_changed_at_set(self, db):
        """Step-down sets last_frequency_changed_at for cooldown tracking."""
        habit = self._accountable_habit(db)
        before = datetime.now(tz=UTC)

        apply_frequency_step_down(db, habit.id, "every_other_day")

        db.refresh(habit)
        assert habit.last_frequency_changed_at is not None
        # SQLite may strip tzinfo — normalize for comparison
        changed_at = habit.last_frequency_changed_at
        if changed_at.tzinfo is None:
            changed_at = changed_at.replace(tzinfo=UTC)
        assert changed_at >= before

    # --- Rejected transitions ---

    def test_skip_level_rejected(self, db):
        """Cannot skip from daily to twice_week."""
        habit = self._accountable_habit(db, "daily")
        with pytest.raises(Exception) as exc_info:
            apply_frequency_step_down(db, habit.id, "twice_week")
        assert exc_info.value.status_code == 400
        assert "Expected exactly one level" in exc_info.value.detail

    def test_backward_rejected(self, db):
        """Cannot go from every_other_day back to daily."""
        habit = self._accountable_habit(db, "every_other_day")
        with pytest.raises(Exception) as exc_info:
            apply_frequency_step_down(db, habit.id, "daily")
        assert exc_info.value.status_code == 400

    def test_weekly_cannot_step_down(self, db):
        """Cannot step down from weekly — that's graduation territory."""
        habit = self._accountable_habit(db, "weekly")
        with pytest.raises(Exception) as exc_info:
            apply_frequency_step_down(db, habit.id, "graduated")
        assert exc_info.value.status_code == 400
        assert "not in the step-down progression" in exc_info.value.detail

    def test_nonexistent_habit_404(self, db):
        """Nonexistent habit_id raises 404."""
        with pytest.raises(Exception) as exc_info:
            apply_frequency_step_down(db, uuid.uuid4(), "every_other_day")
        assert exc_info.value.status_code == 404


# ===========================================================================
# [2G-03] Manual override — cooldown reset via PATCH
# ===========================================================================


class TestManualFrequencyOverrideCooldown:

    def test_manual_change_sets_last_frequency_changed_at(self, client):
        """Changing notification_frequency via PATCH sets last_frequency_changed_at."""
        habit = make_habit(client, notification_frequency="daily",
                          scaffolding_status="accountable")

        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"notification_frequency": "weekly"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notification_frequency"] == "weekly"
        assert data["last_frequency_changed_at"] is not None

    def test_same_frequency_does_not_reset_cooldown(self, client):
        """Setting notification_frequency to the same value does NOT reset cooldown."""
        habit = make_habit(client, notification_frequency="daily",
                          scaffolding_status="accountable")

        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"notification_frequency": "daily"},
        )
        assert resp.status_code == 200
        assert resp.json()["last_frequency_changed_at"] is None

    def test_manual_override_then_cooldown_respected(self, client, db):
        """After manual override, step-down evaluation sees cooldown."""
        habit_data = make_habit(client, notification_frequency="daily",
                                scaffolding_status="accountable")

        # Manual override to weekly
        client.patch(
            f"/api/habits/{habit_data['id']}",
            json={"notification_frequency": "every_other_day"},
        )

        # Create enough notifications for evaluation
        habit_id = uuid.UUID(habit_data["id"])
        for i in range(14):
            _create_notification(
                db, habit_id, "Already done", "responded", days_ago=i + 1,
            )

        result = evaluate_frequency_step_down(db, habit_id)

        assert result.cooldown_active is True
        assert result.recommend_step_down is False
