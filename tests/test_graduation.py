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

from app.models import (
    ActivityLog,
    Domain,
    Habit,
    HabitCompletion,
    NotificationQueue,
    Routine,
)
from app.services.graduation import (
    FrequencyChangeResult,
    FrequencyStepResult,
    GraduationExecutionResult,
    GraduationResult,
    ReScaffoldResult,
    SlipDetectionResult,
    apply_frequency_step_down,
    apply_re_scaffold_tightening,
    evaluate_all_graduated_habits,
    evaluate_frequency_step_down,
    evaluate_graduated_habit_slip,
    evaluate_graduation,
    get_stacking_recommendation,
    graduate_habit,
    next_step_down,
    re_scaffold_habit,
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

    # Phase 2: force-null graduation fields via UPDATE
    if force_null:
        for field in force_null:
            setattr(habit, field, None)
        db.commit()

    db.refresh(habit)
    return habit


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


def _create_completion(db, habit_id: uuid.UUID, days_ago: int = 0) -> HabitCompletion:
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


def _create_routine_checklist(
    db, routine_id: uuid.UUID, response: str | None, status: str, days_ago: int = 5
) -> NotificationQueue:
    """Insert a routine_checklist notification for a routine."""
    n = NotificationQueue(
        id=uuid.uuid4(),
        notification_type="routine_checklist",
        delivery_type="notification",
        status=status,
        scheduled_at=datetime.now(tz=UTC) - timedelta(days=days_ago),
        target_entity_type="routine",
        target_entity_id=routine_id,
        message="Routine checklist time!",
        response=response,
        scheduled_by="system",
    )
    db.add(n)
    db.commit()
    return n


def _create_notification(
    db, habit_id: uuid.UUID, response: str | None, status: str, days_ago: int = 5
) -> NotificationQueue:
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
        habit = _create_habit(
            db,
            graduation_window=None,
            graduation_target=None,
            graduation_threshold=None,
            friction_score=None,
        )
        window, target, threshold = resolve_graduation_params(habit)
        assert (window, target, threshold) == (45, 0.85, 45)

    def test_friction_1_defaults(self, db):
        habit = _create_habit(
            db,
            friction_score=1,
            graduation_window=None,
            graduation_target=None,
            graduation_threshold=None,
        )
        window, target, threshold = resolve_graduation_params(habit)
        assert (window, target, threshold) == (30, 0.85, 30)

    def test_friction_5_defaults(self, db):
        habit = _create_habit(
            db,
            friction_score=5,
            graduation_window=None,
            graduation_target=None,
            graduation_threshold=None,
        )
        window, target, threshold = resolve_graduation_params(habit)
        assert (window, target, threshold) == (60, 0.80, 60)

    def test_per_habit_overrides(self, db):
        """Per-habit values take precedence over friction defaults."""
        habit = _create_habit(
            db,
            friction_score=1,
            graduation_window=90,
            graduation_target=0.70,
            graduation_threshold=90,
        )
        window, target, threshold = resolve_graduation_params(habit)
        assert window == 90
        assert target == 0.70
        assert threshold == 90

    def test_partial_override(self, db):
        """One override, rest from friction tier."""
        habit = _create_habit(
            db,
            friction_score=4,
            graduation_window=100,
            graduation_target=None,
            graduation_threshold=None,
        )
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
        assert w == 37  # int(30 * 1.25)
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
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=60))
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
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=60))
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
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=10))
        for i in range(10):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)

        result = evaluate_graduation(db, habit.id)

        assert result.eligible is False
        assert result.meets_rate is True
        assert result.meets_threshold is False
        assert any("days accountable" in r for r in result.blocking_reasons)

    def test_ineligible_no_notification_data(self, db):
        """Habit with no notifications in window is not eligible."""
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=60))

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

    def test_paused_habit_returns_blocking_reason(self, db):
        """Habit with status != 'active' returns eligible=False with status blocking_reason."""
        habit = _create_habit(
            db, status="paused", scaffolding_status="accountable",
        )

        result = evaluate_graduation(db, habit.id)

        assert result.eligible is False
        assert any(
            "status must be 'active'" in r for r in result.blocking_reasons
        )

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
            accountable_since=date.today() - timedelta(days=60),
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
            accountable_since=date.today() - timedelta(days=60),
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
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=60))
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
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=60))
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
            accountable_since=date.today() - timedelta(days=120),
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

    def test_habit_with_no_accountable_since(self, db):
        """Habit with no accountable_since gets 0 days_accountable."""
        habit = _create_habit(db, accountable_since=None)
        for i in range(10):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)

        result = evaluate_graduation(db, habit.id)

        assert result.days_accountable == 0
        assert result.meets_threshold is False


# ===========================================================================
# D5 hybrid credit — [2G-Bug-02]
# ===========================================================================


class TestEvaluateGraduationHybridCredit:
    """Expired nudges credited by same-date HabitCompletion rows.

    See `[2G-01]` Amendment 12 / brain3#184. Multiple low-friction completion
    paths (direct complete, routine cascade, reconciliation) all count toward
    graduation — explicit responses still win over completion rows.
    """

    def test_routine_cascade_completion_credited_toward_graduation(self, db):
        """Expired nudges with same-date routine_cascade completions credit the rate."""
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=60))
        # 10 expired (unresponded) nudges, each with a matching routine_cascade
        # completion on the same date.
        for i in range(10):
            days_ago = i + 1
            _create_notification(db, habit.id, None, "expired", days_ago=days_ago)
            db.add(
                HabitCompletion(
                    id=uuid.uuid4(),
                    habit_id=habit.id,
                    completed_at=date.today() - timedelta(days=days_ago),
                    source="routine_cascade",
                ),
            )
        db.commit()

        result = evaluate_graduation(db, habit.id)

        assert result.total_notifications == 10
        assert result.already_done_count == 10
        assert result.current_rate == 1.0
        assert result.meets_rate is True
        assert result.eligible is True

    def test_individual_completion_credited_toward_graduation(self, db):
        """Expired nudges with same-date individual completions credit the rate."""
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=60))
        # 10 expired (unresponded) nudges; first 9 have matching individual
        # completions, last 1 does not → 90% hybrid-credited rate.
        for i in range(10):
            days_ago = i + 1
            _create_notification(db, habit.id, None, "expired", days_ago=days_ago)
            if i < 9:
                _create_completion(db, habit.id, days_ago=days_ago)

        result = evaluate_graduation(db, habit.id)

        assert result.total_notifications == 10
        assert result.already_done_count == 9
        assert result.current_rate == 0.9
        assert result.eligible is True

    def test_no_credit_when_no_completion_row(self, db):
        """Regression guard: expired nudges without a matching completion do NOT get credit."""
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=60))
        # 10 expired nudges, zero completions anywhere.
        for i in range(10):
            _create_notification(db, habit.id, None, "expired", days_ago=i + 1)

        result = evaluate_graduation(db, habit.id)

        assert result.total_notifications == 10
        assert result.already_done_count == 0
        assert result.current_rate == 0.0
        assert result.eligible is False
        assert any("below target" in r for r in result.blocking_reasons)

    def test_no_credit_when_date_mismatch(self, db):
        """Completion rows credit only same-date expired nudges."""
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=60))
        # 5 expired nudges on days 1-5. Completions exist, but on days 10-14.
        # Date mismatch → no credit.
        for i in range(5):
            _create_notification(db, habit.id, None, "expired", days_ago=i + 1)
        for i in range(5):
            _create_completion(db, habit.id, days_ago=i + 10)

        result = evaluate_graduation(db, habit.id)

        assert result.total_notifications == 5
        assert result.already_done_count == 0
        assert result.current_rate == 0.0

    def test_response_already_done_still_counts_without_completion_row(self, db):
        """Back-compat: explicit 'Already done' responses count regardless of completion rows."""
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=60))
        # 10 nudges, all explicit "Already done" responses. No completion rows.
        for i in range(10):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)

        result = evaluate_graduation(db, habit.id)

        assert result.total_notifications == 10
        assert result.already_done_count == 10
        assert result.current_rate == 1.0
        assert result.eligible is True

    def test_explicit_negative_response_not_overridden_by_completion(self, db):
        """Explicit non-'Already done' responses win — completion row does NOT override."""
        habit = _create_habit(db, accountable_since=date.today() - timedelta(days=60))
        # 10 notifications all responded "Skip today". Completions exist on
        # every same day. Per spec Acceptance Criterion #4, explicit negative
        # responses are never overridden.
        for i in range(10):
            days_ago = i + 1
            _create_notification(db, habit.id, "Skip today", "responded", days_ago=days_ago)
            _create_completion(db, habit.id, days_ago=days_ago)

        result = evaluate_graduation(db, habit.id)

        assert result.total_notifications == 10
        assert result.already_done_count == 0
        assert result.current_rate == 0.0


# ===========================================================================
# Schema validation — friction_score on create/update
# ===========================================================================


class TestFrictionScoreValidation:
    def test_create_with_valid_friction_score(self, client):
        resp = client.post(
            "/api/habits",
            json={
                "title": "Test",
                "frequency": "daily",
                "friction_score": 3,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["friction_score"] == 3

    def test_create_with_null_friction_score(self, client):
        resp = client.post(
            "/api/habits",
            json={
                "title": "Test",
                "frequency": "daily",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["friction_score"] is None

    def test_create_friction_score_too_low(self, client):
        resp = client.post(
            "/api/habits",
            json={
                "title": "Test",
                "frequency": "daily",
                "friction_score": 0,
            },
        )
        assert resp.status_code == 422

    def test_create_friction_score_too_high(self, client):
        resp = client.post(
            "/api/habits",
            json={
                "title": "Test",
                "frequency": "daily",
                "friction_score": 6,
            },
        )
        assert resp.status_code == 422

    def test_update_friction_score(self, client):
        habit = make_habit(client)
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"friction_score": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["friction_score"] == 5

    def test_update_friction_score_invalid(self, client):
        habit = make_habit(client)
        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"friction_score": 10},
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
            "accountable_since": date.today() - timedelta(days=60),
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
            "accountable_since": date.today() - timedelta(days=60),
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
            db,
            best_streak=15,
            last_completed=date.today() - timedelta(days=1),
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

        log = db.query(ActivityLog).filter(ActivityLog.habit_id == habit.id).first()
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
            db,
            status="paused",
            scaffolding_status="accountable",
            notification_frequency="daily",
        )
        with pytest.raises(Exception) as exc_info:
            graduate_habit(db, habit.id)
        assert exc_info.value.status_code == 400
        assert "paused" in exc_info.value.detail

    def test_abandoned_habit_rejected(self, db):
        """Cannot graduate an abandoned habit."""
        habit = _create_habit(
            db,
            status="abandoned",
            scaffolding_status="accountable",
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
            db,
            scaffolding_status="tracking",
            notification_frequency="daily",
        )
        with pytest.raises(Exception) as exc_info:
            graduate_habit(db, habit.id)
        assert exc_info.value.status_code == 400
        assert "tracking" in exc_info.value.detail

    # --- Already graduated ---

    def test_already_graduated_returns_failure(self, db):
        """Already graduated habit returns success=False (not an exception)."""
        habit = _create_habit(
            db,
            scaffolding_status="graduated",
            notification_frequency="graduated",
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

        log = db.query(ActivityLog).filter(ActivityLog.habit_id == habit.id).first()
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

        log_count = db.query(ActivityLog).filter(ActivityLog.habit_id == habit.id).count()
        assert log_count == 0

    def test_evaluated_graduation_no_forced_label(self, db):
        """Normal (non-forced) graduation does NOT include '(forced)' in activity log."""
        habit = self._eligible_habit(db)
        graduate_habit(db, habit.id)

        log = db.query(ActivityLog).filter(ActivityLog.habit_id == habit.id).first()
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
        self,
        db,
        *,
        notification_frequency="daily",
        already_done=10,
        other_response=4,
        status="active",
        scaffolding_status="accountable",
        last_frequency_changed_at=None,
        **habit_overrides,
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
                db,
                habit.id,
                "Already done",
                "responded",
                days_ago=i + 1,
            )
        for i in range(other_response):
            _create_notification(
                db,
                habit.id,
                "Skip today",
                "responded",
                days_ago=already_done + i + 1,
            )
        return habit

    # --- Recommends step-down ---

    def test_daily_step_down_recommended(self, db):
        """Daily habit with >= 60% already-done rate recommends every_other_day."""
        habit = self._habit_with_notifications(
            db,
            notification_frequency="daily",
            already_done=9,
            other_response=5,
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
            db,
            notification_frequency="every_other_day",
            already_done=10,
            other_response=4,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is True
        assert result.recommended_frequency == "twice_week"

    def test_twice_week_step_down(self, db):
        """twice_week → weekly when rate meets threshold."""
        habit = self._habit_with_notifications(
            db,
            notification_frequency="twice_week",
            already_done=10,
            other_response=4,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is True
        assert result.recommended_frequency == "weekly"

    def test_exact_threshold_recommends(self, db):
        """Exactly 60% rate still recommends step-down."""
        # 6 out of 10 = 60%
        habit = self._habit_with_notifications(
            db,
            notification_frequency="daily",
            already_done=6,
            other_response=4,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is True
        assert result.current_rate == pytest.approx(0.6)

    # --- No recommendation ---

    def test_weekly_no_step_down(self, db):
        """Weekly habit cannot step down further — graduation is separate."""
        habit = self._habit_with_notifications(
            db,
            notification_frequency="weekly",
            already_done=14,
            other_response=0,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert result.recommended_frequency is None
        assert any("minimum stepped frequency" in r for r in result.blocking_reasons)

    def test_graduated_no_step_down(self, db):
        """Graduated frequency is not in the progression."""
        habit = self._habit_with_notifications(
            db,
            notification_frequency="graduated",
            already_done=10,
            other_response=4,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert any("not in the step-down progression" in r for r in result.blocking_reasons)

    def test_none_frequency_no_step_down(self, db):
        """'none' frequency is not in the progression."""
        habit = self._habit_with_notifications(
            db,
            notification_frequency="none",
            already_done=10,
            other_response=4,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False

    def test_rate_below_threshold(self, db):
        """Rate below 60% does not recommend step-down."""
        # 5 out of 14 = ~36%
        habit = self._habit_with_notifications(
            db,
            notification_frequency="daily",
            already_done=5,
            other_response=9,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert result.current_rate == pytest.approx(5 / 14)
        assert any("below step-down threshold" in r for r in result.blocking_reasons)

    def test_insufficient_notifications(self, db):
        """Fewer than 5 notifications returns no recommendation."""
        habit = self._habit_with_notifications(
            db,
            notification_frequency="daily",
            already_done=3,
            other_response=1,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert result.notifications_evaluated == 4
        assert any("Need at least 5" in r for r in result.blocking_reasons)

    def test_zero_notifications(self, db):
        """No notifications at all returns no recommendation."""
        habit = self._habit_with_notifications(
            db,
            notification_frequency="daily",
            already_done=0,
            other_response=0,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert result.notifications_evaluated == 0

    # --- Cooldown ---

    def test_cooldown_active(self, db):
        """Habit with recent frequency change is in cooldown."""
        recent = datetime.now(tz=UTC) - timedelta(days=3)
        habit = self._habit_with_notifications(
            db,
            notification_frequency="daily",
            already_done=14,
            other_response=0,
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
            db,
            notification_frequency="daily",
            already_done=14,
            other_response=0,
            last_frequency_changed_at=old,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is True
        assert result.cooldown_active is False

    def test_cooldown_exactly_7_days(self, db):
        """Frequency change exactly 7 days ago — cooldown has expired."""
        boundary = datetime.now(tz=UTC) - timedelta(days=7)
        habit = self._habit_with_notifications(
            db,
            notification_frequency="daily",
            already_done=14,
            other_response=0,
            last_frequency_changed_at=boundary,
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is True
        assert result.cooldown_active is False

    # --- Status gates ---

    def test_paused_habit_rejected(self, db):
        """Paused habits are not evaluated for step-down."""
        habit = self._habit_with_notifications(
            db,
            notification_frequency="daily",
            already_done=14,
            other_response=0,
            status="paused",
        )
        result = evaluate_frequency_step_down(db, habit.id)

        assert result.recommend_step_down is False
        assert any("active" in r for r in result.blocking_reasons)

    def test_tracking_scaffolding_rejected(self, db):
        """Tracking habits are not evaluated for step-down."""
        habit = self._habit_with_notifications(
            db,
            notification_frequency="daily",
            already_done=14,
            other_response=0,
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
                db,
                habit.id,
                "Already done",
                "responded",
                days_ago=i + 1,
            )
        # 10 older "Skip today" — should be excluded by LIMIT
        for i in range(10):
            _create_notification(
                db,
                habit.id,
                "Skip today",
                "responded",
                days_ago=20 + i,
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
                db,
                habit.id,
                "Already done",
                "responded",
                days_ago=i + 1,
            )
        _create_notification(db, habit.id, None, "pending", days_ago=1)
        _create_notification(db, habit.id, None, "delivered", days_ago=1)

        result = evaluate_frequency_step_down(db, habit.id)

        assert result.notifications_evaluated == 10


# ===========================================================================
# D6 hybrid credit — [2G-Bug-03]
# ===========================================================================


class TestEvaluateFrequencyStepDownHybridCredit:
    """Expired nudges credited by same-date HabitCompletion rows.

    See `[2G-03]` Amendment 15 / brain3#185. Mirrors D5 in `[2G-01]` / #184 —
    same ADHD quality lens: multiple low-friction completion paths feel like
    "I did it" and should all count toward step-down rate, regardless of
    which channel recorded the completion.
    """

    def test_routine_cascade_completion_credited_toward_step_down(self, db):
        """14 expired nudges with matching routine_cascade completions → 100% rate, step down."""
        habit = _create_habit(db, notification_frequency="daily")
        for i in range(14):
            days_ago = i + 1
            _create_notification(db, habit.id, None, "expired", days_ago=days_ago)
            db.add(
                HabitCompletion(
                    id=uuid.uuid4(),
                    habit_id=habit.id,
                    completed_at=date.today() - timedelta(days=days_ago),
                    source="routine_cascade",
                ),
            )
        db.commit()

        result = evaluate_frequency_step_down(db, habit.id)

        assert result.notifications_evaluated == 14
        assert result.current_rate == 1.0
        assert result.recommend_step_down is True
        assert result.recommended_frequency == "every_other_day"
        assert result.blocking_reasons == []

    def test_no_credit_when_no_completion_row_step_down(self, db):
        """Regression guard: expired nudges with no completions don't get hybrid credit."""
        habit = _create_habit(db, notification_frequency="daily")
        for i in range(14):
            _create_notification(db, habit.id, None, "expired", days_ago=i + 1)

        result = evaluate_frequency_step_down(db, habit.id)

        assert result.notifications_evaluated == 14
        assert result.current_rate == 0.0
        assert result.recommend_step_down is False
        assert any("below step-down threshold" in r for r in result.blocking_reasons)

    def test_mixed_response_and_completion_step_down(self, db):
        """7 'Already done' + 7 expired-with-matching-completion → 100% rate."""
        habit = _create_habit(db, notification_frequency="daily")
        # First 7 days: explicit "Already done" responses, no completion rows needed
        for i in range(7):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        # Next 7 days: expired nudges with matching routine_cascade completions
        for i in range(7):
            days_ago = 8 + i
            _create_notification(db, habit.id, None, "expired", days_ago=days_ago)
            db.add(
                HabitCompletion(
                    id=uuid.uuid4(),
                    habit_id=habit.id,
                    completed_at=date.today() - timedelta(days=days_ago),
                    source="routine_cascade",
                ),
            )
        db.commit()

        result = evaluate_frequency_step_down(db, habit.id)

        assert result.notifications_evaluated == 14
        assert result.current_rate == 1.0
        assert result.recommend_step_down is True
        assert result.recommended_frequency == "every_other_day"

    def test_same_day_nudge_and_completion_not_double_counted(self, db):
        """De-dup rule: explicit 'Already done' + same-date completion counts once, not twice.

        Denominator stays at nudge count; credit caps at total_evaluated.
        """
        habit = _create_habit(db, notification_frequency="daily")
        for i in range(14):
            days_ago = i + 1
            _create_notification(db, habit.id, "Already done", "responded", days_ago=days_ago)
            db.add(
                HabitCompletion(
                    id=uuid.uuid4(),
                    habit_id=habit.id,
                    completed_at=date.today() - timedelta(days=days_ago),
                    source="individual",
                ),
            )
        db.commit()

        result = evaluate_frequency_step_down(db, habit.id)

        assert result.notifications_evaluated == 14
        assert result.current_rate == 1.0

    def test_explicit_negative_response_not_overridden_by_completion_step_down(self, db):
        """Explicit non-'Already done' responses win — completion row does NOT override."""
        habit = _create_habit(db, notification_frequency="daily")
        for i in range(14):
            days_ago = i + 1
            _create_notification(db, habit.id, "Skip today", "responded", days_ago=days_ago)
            _create_completion(db, habit.id, days_ago=days_ago)

        result = evaluate_frequency_step_down(db, habit.id)

        assert result.notifications_evaluated == 14
        assert result.current_rate == 0.0
        assert result.recommend_step_down is False

    def test_extra_completions_outside_nudge_range_do_not_inflate_denominator(self, db):
        """Completion rows do NOT inflate total_evaluated — denominator stays nudge count."""
        habit = _create_habit(db, notification_frequency="daily")
        # 14 expired nudges on days 1-14 + 14 matching completions
        for i in range(14):
            days_ago = i + 1
            _create_notification(db, habit.id, None, "expired", days_ago=days_ago)
            _create_completion(db, habit.id, days_ago=days_ago)
        # Extra completions on days 20-25 with no matching nudges — should be ignored
        for i in range(6):
            _create_completion(db, habit.id, days_ago=20 + i)

        result = evaluate_frequency_step_down(db, habit.id)

        assert result.notifications_evaluated == 14
        assert result.current_rate == 1.0

    def test_stacking_stability_inherits_step_down_rate_change(self, db):
        """Transitive: _assess_habit_stability via step-down rate now reflects completion credit.

        A routine-cascade-completed habit with no explicit nudge responses used to be
        'not stable' (rate 0%); after D6 it's stable (rate 100%) via the first OR'd
        criterion in _assess_habit_stability. Verified through the public
        get_stacking_recommendation path — the habit is not in blocking_habits.

        The habit is intentionally set up to fail criterion 2 (14+ days accountable,
        7-day completion streak) so criterion 1 is the only path to stability:
        accountable_since=10 days ago means criterion 2 cannot save it.
        """
        routine = _create_routine(db)
        # accountable_since=10 days: fails stacking criterion 2 (needs 14+).
        habit = _create_habit(
            db,
            routine_id=routine.id,
            notification_frequency="daily",
            scaffolding_status="accountable",
            accountable_since=date.today() - timedelta(days=10),
        )
        for i in range(14):
            days_ago = i + 1
            _create_notification(db, habit.id, None, "expired", days_ago=days_ago)
            db.add(
                HabitCompletion(
                    id=uuid.uuid4(),
                    habit_id=habit.id,
                    completed_at=date.today() - timedelta(days=days_ago),
                    source="routine_cascade",
                ),
            )
        db.commit()

        recommendation = get_stacking_recommendation(db, routine.id)

        # Habit is stable → not in blocking_habits → routine ready for next stack.
        assert recommendation.blocking_habits == []
        assert recommendation.ready is True
        stability_entries = [
            s for s in recommendation.active_accountable_habits if s.habit_id == habit.id
        ]
        assert len(stability_entries) == 1
        assert stability_entries[0].is_stable is True


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

        log = db.query(ActivityLog).filter(ActivityLog.habit_id == habit.id).first()
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
        habit = make_habit(client, notification_frequency="daily", scaffolding_status="accountable")

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
        habit = make_habit(client, notification_frequency="daily", scaffolding_status="accountable")

        resp = client.patch(
            f"/api/habits/{habit['id']}",
            json={"notification_frequency": "daily"},
        )
        assert resp.status_code == 200
        assert resp.json()["last_frequency_changed_at"] is None

    def test_manual_override_then_cooldown_respected(self, client, db):
        """After manual override, step-down evaluation sees cooldown."""
        habit_data = make_habit(
            client, notification_frequency="daily", scaffolding_status="accountable"
        )

        # Manual override to weekly
        client.patch(
            f"/api/habits/{habit_data['id']}",
            json={"notification_frequency": "every_other_day"},
        )

        # Create enough notifications for evaluation
        habit_id = uuid.UUID(habit_data["id"])
        for i in range(14):
            _create_notification(
                db,
                habit_id,
                "Already done",
                "responded",
                days_ago=i + 1,
            )

        result = evaluate_frequency_step_down(db, habit_id)

        assert result.cooldown_active is True
        assert result.recommend_step_down is False


# ===========================================================================
# [2G-04] evaluate_graduated_habit_slip
# ===========================================================================


class TestEvaluateGraduatedHabitSlip:
    """Tests for slip detection on graduated habits."""

    def _graduated_habit(self, db, *, routine_id=None, **overrides) -> Habit:
        """Create a graduated habit."""
        defaults = {
            "scaffolding_status": "graduated",
            "notification_frequency": "graduated",
            "status": "active",
            "accountable_since": date.today() - timedelta(days=90),
            "routine_id": routine_id,
        }
        defaults.update(overrides)
        return _create_habit(db, **defaults)

    # --- No slip ---

    def test_no_slip_with_recent_completions(self, db):
        """Graduated habit with recent completions shows no slip."""
        habit = self._graduated_habit(db)
        # Completions in the last 7 days
        for i in range(5):
            _create_completion(db, habit.id, days_ago=i + 1)

        result = evaluate_graduated_habit_slip(db, habit.id)

        assert isinstance(result, SlipDetectionResult)
        assert result.slip_detected is False
        assert result.recommendation == "no_action"
        assert result.slip_signals == []
        assert "holding steady" in result.message

    def test_no_action_for_non_graduated_habit(self, db):
        """Accountable habit returns no_action — slip detection only applies to graduated."""
        habit = _create_habit(db, scaffolding_status="accountable")

        result = evaluate_graduated_habit_slip(db, habit.id)

        assert result.slip_detected is False
        assert result.recommendation == "no_action"
        assert "not graduated" in result.message

    def test_nonexistent_habit_raises(self, db):
        """Evaluating a nonexistent habit raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            evaluate_graduated_habit_slip(db, uuid.uuid4())

    # --- Signal 2: No completion recorded (standalone habit) ---

    def test_warning_no_completions_7_days(self, db):
        """0 completions in last 7 days but some in 14-day window → warning."""
        habit = self._graduated_habit(db)
        # Completion 10 days ago (within 14-day window, outside 7-day window)
        _create_completion(db, habit.id, days_ago=10)

        result = evaluate_graduated_habit_slip(db, habit.id)

        assert result.slip_detected is True
        assert result.recommendation == "monitor"
        assert len(result.slip_signals) == 1
        signal = result.slip_signals[0]
        assert signal.signal_type == "no_completion_recorded"
        assert signal.severity == "warning"

    def test_critical_no_completions_14_days(self, db):
        """0 completions in 14 days → critical."""
        habit = self._graduated_habit(db)
        # No completions at all

        result = evaluate_graduated_habit_slip(db, habit.id)

        assert result.slip_detected is True
        assert result.recommendation == "re_scaffold"
        assert len(result.slip_signals) == 1
        signal = result.slip_signals[0]
        assert signal.signal_type == "no_completion_recorded"
        assert signal.severity == "critical"
        assert "Re-scaffolding recommended" in result.message

    def test_no_warning_with_recent_completions_within_7_days(self, db):
        """Completions within 7 days → no completion signal."""
        habit = self._graduated_habit(db)
        _create_completion(db, habit.id, days_ago=3)

        result = evaluate_graduated_habit_slip(db, habit.id)

        assert result.slip_detected is False
        assert result.recommendation == "no_action"

    # --- Signal 1: Missed in routine checklists ---

    def test_standalone_habit_only_signal_2(self, db):
        """Standalone habits (no routine) only evaluate Signal 2."""
        habit = self._graduated_habit(db, routine_id=None)
        _create_completion(db, habit.id, days_ago=2)

        result = evaluate_graduated_habit_slip(db, habit.id)

        assert result.slip_detected is False
        # No checklist signals even if we somehow had checklist notifications
        assert all(s.signal_type != "missed_in_checklist" for s in result.slip_signals)

    def test_checklist_warning_3_misses(self, db):
        """3 partial/expired routine checklists in 14 days → warning signal."""
        routine = _create_routine(db)
        habit = self._graduated_habit(db, routine_id=routine.id)
        # Recent completions to avoid Signal 2
        for i in range(3):
            _create_completion(db, habit.id, days_ago=i + 1)
        # 3 partial checklist responses
        for i in range(3):
            _create_routine_checklist(
                db,
                routine.id,
                "Partial",
                "responded",
                days_ago=i + 1,
            )

        result = evaluate_graduated_habit_slip(db, habit.id)

        assert result.slip_detected is True
        assert result.recommendation == "monitor"
        checklist_signals = [
            s for s in result.slip_signals if s.signal_type == "missed_in_checklist"
        ]
        assert len(checklist_signals) == 1
        assert checklist_signals[0].severity == "warning"

    def test_checklist_critical_5_misses(self, db):
        """5+ partial/expired routine checklists in 14 days → critical signal."""
        routine = _create_routine(db)
        habit = self._graduated_habit(db, routine_id=routine.id)
        # Recent completions to avoid Signal 2
        for i in range(5):
            _create_completion(db, habit.id, days_ago=i + 1)
        # 5 partial/expired checklist responses
        for i in range(3):
            _create_routine_checklist(
                db,
                routine.id,
                "Partial",
                "responded",
                days_ago=i + 1,
            )
        for i in range(2):
            _create_routine_checklist(
                db,
                routine.id,
                None,
                "expired",
                days_ago=i + 4,
            )

        result = evaluate_graduated_habit_slip(db, habit.id)

        assert result.slip_detected is True
        checklist_signals = [
            s for s in result.slip_signals if s.signal_type == "missed_in_checklist"
        ]
        assert len(checklist_signals) == 1
        assert checklist_signals[0].severity == "critical"
        assert result.recommendation == "re_scaffold"

    def test_checklist_2_misses_no_signal(self, db):
        """Only 2 misses — below threshold, no signal."""
        routine = _create_routine(db)
        habit = self._graduated_habit(db, routine_id=routine.id)
        for i in range(3):
            _create_completion(db, habit.id, days_ago=i + 1)
        for i in range(2):
            _create_routine_checklist(
                db,
                routine.id,
                "Partial",
                "responded",
                days_ago=i + 1,
            )

        result = evaluate_graduated_habit_slip(db, habit.id)

        checklist_signals = [
            s for s in result.slip_signals if s.signal_type == "missed_in_checklist"
        ]
        assert len(checklist_signals) == 0

    def test_expired_checklists_count_as_misses(self, db):
        """Expired (unanswered) routine checklists count toward miss threshold."""
        routine = _create_routine(db)
        habit = self._graduated_habit(db, routine_id=routine.id)
        for i in range(3):
            _create_completion(db, habit.id, days_ago=i + 1)
        # 3 expired checklists
        for i in range(3):
            _create_routine_checklist(
                db,
                routine.id,
                None,
                "expired",
                days_ago=i + 1,
            )

        result = evaluate_graduated_habit_slip(db, habit.id)

        checklist_signals = [
            s for s in result.slip_signals if s.signal_type == "missed_in_checklist"
        ]
        assert len(checklist_signals) == 1
        assert checklist_signals[0].severity == "warning"

    # --- Combined signals ---

    def test_critical_from_both_signals(self, db):
        """Both critical signals present → re_scaffold recommendation."""
        routine = _create_routine(db)
        habit = self._graduated_habit(db, routine_id=routine.id)
        # No completions (Signal 2 critical)
        # 5 partial checklists (Signal 1 critical)
        for i in range(5):
            _create_routine_checklist(
                db,
                routine.id,
                "Partial",
                "responded",
                days_ago=i + 1,
            )

        result = evaluate_graduated_habit_slip(db, habit.id)

        assert result.slip_detected is True
        assert result.recommendation == "re_scaffold"
        assert len(result.slip_signals) == 2

    def test_monitor_with_only_warnings(self, db):
        """Warning-only signals → monitor recommendation."""
        routine = _create_routine(db)
        habit = self._graduated_habit(db, routine_id=routine.id)
        # Completion 10 days ago (Signal 2 warning)
        _create_completion(db, habit.id, days_ago=10)
        # 3 partial checklists (Signal 1 warning)
        for i in range(3):
            _create_routine_checklist(
                db,
                routine.id,
                "Partial",
                "responded",
                days_ago=i + 1,
            )

        result = evaluate_graduated_habit_slip(db, habit.id)

        assert result.slip_detected is True
        assert result.recommendation == "monitor"
        assert len(result.slip_signals) == 2

    def test_critical_overrides_warning(self, db):
        """If any signal is critical, recommendation is re_scaffold even if others are warning."""
        routine = _create_routine(db)
        habit = self._graduated_habit(db, routine_id=routine.id)
        # No completions → critical (Signal 2)
        # 3 partial checklists → warning only (Signal 1)
        for i in range(3):
            _create_routine_checklist(
                db,
                routine.id,
                "Partial",
                "responded",
                days_ago=i + 1,
            )

        result = evaluate_graduated_habit_slip(db, habit.id)

        assert result.recommendation == "re_scaffold"
        severities = {s.severity for s in result.slip_signals}
        assert "critical" in severities
        assert "warning" in severities

    def test_completed_checklists_not_counted(self, db):
        """Checklists with response='Complete' or status='responded' (not Partial) don't count."""
        routine = _create_routine(db)
        habit = self._graduated_habit(db, routine_id=routine.id)
        for i in range(3):
            _create_completion(db, habit.id, days_ago=i + 1)
        # 5 complete checklists — should NOT trigger
        for i in range(5):
            _create_routine_checklist(
                db,
                routine.id,
                "Complete",
                "responded",
                days_ago=i + 1,
            )

        result = evaluate_graduated_habit_slip(db, habit.id)

        checklist_signals = [
            s for s in result.slip_signals if s.signal_type == "missed_in_checklist"
        ]
        assert len(checklist_signals) == 0


# ===========================================================================
# [2G-04] evaluate_all_graduated_habits
# ===========================================================================


class TestEvaluateAllGraduatedHabits:
    def test_returns_only_actionable(self, db):
        """Only habits with recommendation != 'no_action' are returned."""
        # Graduated habit with recent completions (no slip)
        good = _create_habit(
            db,
            scaffolding_status="graduated",
            notification_frequency="graduated",
            status="active",
            accountable_since=date.today() - timedelta(days=90),
        )
        for i in range(5):
            _create_completion(db, good.id, days_ago=i + 1)

        # Graduated habit with no completions (critical slip)
        bad = _create_habit(
            db,
            scaffolding_status="graduated",
            notification_frequency="graduated",
            status="active",
            accountable_since=date.today() - timedelta(days=90),
            title="Slipping Habit",
        )

        results = evaluate_all_graduated_habits(db)

        assert len(results) == 1
        assert results[0].habit_id == bad.id
        assert results[0].recommendation == "re_scaffold"

    def test_excludes_non_graduated(self, db):
        """Accountable and tracking habits are not evaluated."""
        _create_habit(
            db,
            scaffolding_status="accountable",
            status="active",
        )
        _create_habit(
            db,
            scaffolding_status="tracking",
            status="active",
        )

        results = evaluate_all_graduated_habits(db)

        assert results == []

    def test_excludes_inactive(self, db):
        """Paused graduated habits are not evaluated."""
        _create_habit(
            db,
            scaffolding_status="graduated",
            notification_frequency="graduated",
            status="paused",
        )

        results = evaluate_all_graduated_habits(db)

        assert results == []

    def test_empty_when_no_graduated(self, db):
        """No graduated habits → empty list."""
        results = evaluate_all_graduated_habits(db)

        assert results == []

    def test_multiple_slipping_habits(self, db):
        """Multiple slipping habits all appear in results."""
        for i in range(3):
            _create_habit(
                db,
                scaffolding_status="graduated",
                notification_frequency="graduated",
                status="active",
                accountable_since=date.today() - timedelta(days=90),
                title=f"Slipping {i}",
            )

        results = evaluate_all_graduated_habits(db)

        assert len(results) == 3


# ===========================================================================
# [2G-04] re_scaffold_habit
# ===========================================================================


class TestReScaffoldHabit:
    def _graduated_habit(self, db, **overrides) -> Habit:
        """Create a graduated, active habit."""
        defaults = {
            "scaffolding_status": "graduated",
            "notification_frequency": "graduated",
            "status": "active",
            "accountable_since": date.today() - timedelta(days=90),
            "friction_score": 1,
            "graduation_window": None,
            "graduation_target": None,
            "graduation_threshold": None,
        }
        defaults.update(overrides)
        return _create_habit(db, **defaults)

    # --- Successful re-scaffold ---

    def test_successful_re_scaffold(self, db):
        """Re-scaffold transitions status and frequency correctly."""
        habit = self._graduated_habit(db)

        result = re_scaffold_habit(db, habit.id)

        assert isinstance(result, ReScaffoldResult)
        assert result.success is True
        assert result.previous_scaffolding_status == "graduated"
        assert result.previous_notification_frequency == "graduated"
        assert result.new_notification_frequency == "daily"
        assert result.re_scaffold_count == 1

        db.refresh(habit)
        assert habit.scaffolding_status == "accountable"
        assert habit.notification_frequency == "daily"

    def test_re_scaffold_increments_count(self, db):
        """re_scaffold_count is incremented."""
        habit = self._graduated_habit(db)
        assert habit.re_scaffold_count == 0

        result = re_scaffold_habit(db, habit.id)

        assert result.re_scaffold_count == 1
        db.refresh(habit)
        assert habit.re_scaffold_count == 1

    def test_re_scaffold_resets_cooldown(self, db):
        """last_frequency_changed_at is set on re-scaffold."""
        habit = self._graduated_habit(db)
        assert habit.last_frequency_changed_at is None

        before = datetime.now(tz=UTC)
        re_scaffold_habit(db, habit.id)
        db.refresh(habit)

        assert habit.last_frequency_changed_at is not None
        changed_at = habit.last_frequency_changed_at
        if changed_at.tzinfo is None:
            changed_at = changed_at.replace(tzinfo=UTC)
        assert changed_at >= before

    def test_re_scaffold_preserves_streaks(self, db):
        """best_streak and last_completed are NOT reset."""
        habit = self._graduated_habit(db)
        habit.best_streak = 21
        habit.last_completed = date.today() - timedelta(days=3)
        db.commit()
        db.refresh(habit)

        re_scaffold_habit(db, habit.id)
        db.refresh(habit)

        assert habit.best_streak == 21
        assert habit.last_completed == date.today() - timedelta(days=3)

    def test_tightened_params_in_result(self, db):
        """Result includes correctly computed tightened graduation criteria."""
        habit = self._graduated_habit(db, friction_score=1)

        result = re_scaffold_habit(db, habit.id)

        # Friction-1 base: (30, 0.85, 30) → 1 re-scaffold: (37, 0.90, 37)
        assert result.tightened_params["window_days"] == 37
        assert result.tightened_params["target_rate"] == pytest.approx(0.90)
        assert result.tightened_params["threshold_days"] == 37

    def test_activity_log_created(self, db):
        """Re-scaffold creates an activity log with action_type='reflected'."""
        habit = self._graduated_habit(db)

        re_scaffold_habit(db, habit.id)

        log = db.query(ActivityLog).filter(ActivityLog.habit_id == habit.id).first()
        assert log is not None
        assert log.action_type == "reflected"
        assert "re-scaffolded" in log.notes
        assert habit.title in log.notes
        assert "#1" in log.notes
        assert "daily" in log.notes.lower()

    # --- Double re-scaffold (compounded tightening) ---

    def test_double_re_scaffold(self, db):
        """Second re-scaffold compounds tightening correctly."""
        habit = self._graduated_habit(db, friction_score=1)

        # First re-scaffold
        result1 = re_scaffold_habit(db, habit.id)
        assert result1.re_scaffold_count == 1

        # Simulate re-graduation (set back to graduated)
        habit.scaffolding_status = "graduated"
        habit.notification_frequency = "graduated"
        db.commit()
        db.refresh(habit)

        # Second re-scaffold
        result2 = re_scaffold_habit(db, habit.id)

        assert result2.re_scaffold_count == 2
        # Friction-1: (30, 0.85, 30) → 2x tightening: (46, 0.95, 46)
        assert result2.tightened_params["window_days"] == 46
        assert result2.tightened_params["target_rate"] == pytest.approx(0.95)
        assert result2.tightened_params["threshold_days"] == 46

        db.refresh(habit)
        assert habit.scaffolding_status == "accountable"
        assert habit.notification_frequency == "daily"

    # --- Rejection cases ---

    def test_reject_non_graduated(self, db):
        """Cannot re-scaffold a non-graduated habit."""
        habit = _create_habit(db, scaffolding_status="accountable", status="active")

        with pytest.raises(Exception) as exc_info:
            re_scaffold_habit(db, habit.id)
        assert exc_info.value.status_code == 400
        assert "accountable" in exc_info.value.detail

    def test_reject_paused(self, db):
        """Cannot re-scaffold a paused habit."""
        habit = _create_habit(
            db,
            scaffolding_status="graduated",
            notification_frequency="graduated",
            status="paused",
        )

        with pytest.raises(Exception) as exc_info:
            re_scaffold_habit(db, habit.id)
        assert exc_info.value.status_code == 400
        assert "paused" in exc_info.value.detail

    def test_reject_tracking(self, db):
        """Cannot re-scaffold a tracking habit."""
        habit = _create_habit(db, scaffolding_status="tracking", status="active")

        with pytest.raises(Exception) as exc_info:
            re_scaffold_habit(db, habit.id)
        assert exc_info.value.status_code == 400
        assert "tracking" in exc_info.value.detail

    def test_nonexistent_habit_404(self, db):
        """Nonexistent habit_id raises 404."""
        with pytest.raises(Exception) as exc_info:
            re_scaffold_habit(db, uuid.uuid4())
        assert exc_info.value.status_code == 404


# ===========================================================================
# [2G-05] Stacking Recommendation Engine
# ===========================================================================


class TestGetStackingRecommendation:
    """Tests for get_stacking_recommendation()."""

    def test_nonexistent_routine_404(self, db):
        """Nonexistent routine_id raises 404."""
        with pytest.raises(Exception) as exc_info:
            get_stacking_recommendation(db, uuid.uuid4())
        assert exc_info.value.status_code == 404

    def test_freeform_routine_no_habits(self, db):
        """Routine with no habits returns ready=True, no suggestion."""
        routine = _create_routine(db)
        result = get_stacking_recommendation(db, routine.id)

        assert result.ready is True
        assert result.suggested_next is None
        assert result.active_accountable_habits == []
        assert result.blocking_habits == []
        assert "freeform" in result.message.lower()

    def test_no_accountable_habits_ready(self, db):
        """Routine with only tracking habits returns ready=True."""
        routine = _create_routine(db)
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            title="Tracking Habit",
        )
        result = get_stacking_recommendation(db, routine.id)

        assert result.ready is True
        assert result.active_accountable_habits == []
        assert result.blocking_habits == []
        assert "no habits are in the accountability loop" in result.message.lower()
        assert result.suggested_next is not None
        assert result.suggested_next.habit_name == "Tracking Habit"
        assert result.suggested_next.source == "queued"

    def test_all_accountable_stable_rate(self, db):
        """Ready when all accountable habits have >= 60% already-done rate."""
        routine = _create_routine(db)
        habit = _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="accountable",
            title="Stable Habit",
            notification_frequency="daily",
            accountable_since=date.today() - timedelta(days=30),
        )
        # Create 10 notifications: 7 "Already done" = 70% rate
        for i in range(7):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        for i in range(3):
            _create_notification(db, habit.id, "Done now", "responded", days_ago=i + 8)

        # Add a tracking habit to be suggested
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            title="Next Habit",
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.ready is True
        assert len(result.active_accountable_habits) == 1
        assert result.active_accountable_habits[0].is_stable is True
        assert result.blocking_habits == []
        assert result.suggested_next is not None
        assert result.suggested_next.habit_name == "Next Habit"
        assert "ready to add" in result.message.lower()

    def test_accountable_habit_at_weekly_is_stable(self, db):
        """A habit at weekly frequency is stable regardless of rate."""
        routine = _create_routine(db)
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="accountable",
            title="Weekly Habit",
            notification_frequency="weekly",
            accountable_since=date.today() - timedelta(days=30),
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.ready is True
        assert len(result.active_accountable_habits) == 1
        assert result.active_accountable_habits[0].is_stable is True
        assert "weekly" in result.active_accountable_habits[0].stability_detail.lower()

    def test_accountable_habit_stable_by_completions(self, db):
        """Stable via 14+ days accountable with 7 consecutive completions."""
        routine = _create_routine(db)
        habit = _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="accountable",
            title="Consistent Habit",
            notification_frequency="daily",
            accountable_since=date.today() - timedelta(days=20),
        )
        # No notifications (rate would be 0), but 7 completions in last 7 days
        for i in range(7):
            _create_completion(db, habit.id, days_ago=i)

        result = get_stacking_recommendation(db, routine.id)

        assert result.ready is True
        assert result.active_accountable_habits[0].is_stable is True
        detail = result.active_accountable_habits[0].stability_detail
        assert "no missed completions" in detail.lower()

    def test_one_blocking_habit(self, db):
        """Not ready when an accountable habit has low rate and no completions."""
        routine = _create_routine(db)
        habit = _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="accountable",
            title="Struggling Habit",
            notification_frequency="daily",
            accountable_since=date.today() - timedelta(days=10),
        )
        # 10 notifications: 3 "Already done" = 30% rate (below 60%)
        for i in range(3):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        for i in range(7):
            _create_notification(db, habit.id, "Done now", "responded", days_ago=i + 4)

        result = get_stacking_recommendation(db, routine.id)

        assert result.ready is False
        assert len(result.blocking_habits) == 1
        assert result.blocking_habits[0].habit_name == "Struggling Habit"
        assert "hold steady" in result.message.lower()

    def test_paused_before_tracking_priority(self, db):
        """Paused tracking habits are suggested before active tracking habits."""
        routine = _create_routine(db)

        # Active tracking habit created first
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="active",
            title="Active Tracking",
        )

        # Paused tracking habit
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="paused",
            title="Paused Tracking",
            accountable_since=date.today() - timedelta(days=30),
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.ready is True
        assert result.suggested_next is not None
        assert result.suggested_next.habit_name == "Paused Tracking"
        assert result.suggested_next.source == "paused"

    def test_paused_ordered_by_accountable_since(self, db):
        """Multiple paused habits: oldest accountable_since is suggested first."""
        routine = _create_routine(db)

        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="paused",
            title="Newer Paused",
            accountable_since=date.today() - timedelta(days=5),
        )
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="paused",
            title="Older Paused",
            accountable_since=date.today() - timedelta(days=30),
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.suggested_next is not None
        assert result.suggested_next.habit_name == "Older Paused"

    def test_tracking_ordered_by_created_at(self, db):
        """Multiple tracking habits: ordered by created_at (position proxy)."""
        routine = _create_routine(db)

        # Create in order — first created should be suggested
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="active",
            title="First Tracking",
        )
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="active",
            title="Second Tracking",
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.suggested_next is not None
        assert result.suggested_next.habit_name == "First Tracking"
        assert result.suggested_next.source == "queued"

    def test_all_graduated_no_suggestion(self, db):
        """All habits graduated — ready but nothing to suggest."""
        routine = _create_routine(db)
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="graduated",
            status="active",
            title="Graduated One",
            notification_frequency="graduated",
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.ready is True
        assert result.suggested_next is None
        assert result.active_accountable_habits == []
        assert "no habits are in the accountability loop" in result.message.lower()

    def test_all_accountable_or_graduated_no_suggestion(self, db):
        """All habits are either accountable (stable) or graduated — no tracking left."""
        routine = _create_routine(db)
        # Stable accountable habit (weekly)
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="accountable",
            title="Weekly Habit",
            notification_frequency="weekly",
        )
        # Graduated habit
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="graduated",
            status="active",
            title="Graduated",
            notification_frequency="graduated",
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.ready is True
        assert result.suggested_next is None
        assert "pipeline" in result.message.lower()

    def test_routine_name_in_response(self, db):
        """Response includes the routine name."""
        routine = _create_routine(db)
        result = get_stacking_recommendation(db, routine.id)

        assert result.routine_id == routine.id
        assert result.routine_name == routine.title

    def test_mixed_stable_and_blocking(self, db):
        """One stable + one blocking = not ready."""
        routine = _create_routine(db)

        # Stable habit (weekly)
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="accountable",
            title="Stable One",
            notification_frequency="weekly",
        )
        # Blocking habit (low rate, few days)
        blocking = _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="accountable",
            title="Needs Work",
            notification_frequency="daily",
            accountable_since=date.today() - timedelta(days=5),
        )
        for i in range(6):
            _create_notification(db, blocking.id, "Done now", "responded", days_ago=i + 1)

        result = get_stacking_recommendation(db, routine.id)

        assert result.ready is False
        assert len(result.active_accountable_habits) == 2
        assert len(result.blocking_habits) == 1
        assert result.blocking_habits[0].habit_name == "Needs Work"


# ===========================================================================
# [2G-fix-01] graduated_at timestamp lifecycle
# ===========================================================================


class TestGraduatedAtTimestamp:
    """Tests for the graduated_at column added by 2G-fix-01."""

    def _eligible_habit(self, db, **overrides) -> Habit:
        """Create an accountable habit that meets graduation criteria."""
        defaults = {
            "scaffolding_status": "accountable",
            "notification_frequency": "daily",
            "accountable_since": date.today() - timedelta(days=60),
            "friction_score": 1,
        }
        defaults.update(overrides)
        habit = _create_habit(db, **defaults)
        # 10 notifications, 9 "Already done" = 90% rate (mirrors TestGraduateHabit)
        for i in range(9):
            _create_notification(db, habit.id, "Already done", "responded", days_ago=i + 1)
        _create_notification(db, habit.id, "Skip today", "responded", days_ago=10)
        return habit

    def test_graduation_sets_graduated_at(self, db):
        """graduate_habit() sets graduated_at to a UTC timestamp."""
        habit = self._eligible_habit(db)
        assert habit.graduated_at is None

        before = datetime.now(tz=UTC)
        graduate_habit(db, habit.id)
        after = datetime.now(tz=UTC)

        db.refresh(habit)
        assert habit.graduated_at is not None
        # SQLite returns naive datetimes — normalize for comparison
        grad_ts = habit.graduated_at
        if grad_ts.tzinfo is None:
            grad_ts = grad_ts.replace(tzinfo=UTC)
        assert before <= grad_ts <= after

    def test_forced_graduation_sets_graduated_at(self, db):
        """Forced graduation also sets graduated_at."""
        habit = _create_habit(
            db,
            scaffolding_status="accountable",
            notification_frequency="daily",
            accountable_since=date.today() - timedelta(days=5),
        )

        graduate_habit(db, habit.id, force=True)
        db.refresh(habit)

        assert habit.graduated_at is not None

    def test_already_graduated_does_not_update_graduated_at(self, db):
        """Idempotent guard: re-graduating doesn't overwrite graduated_at."""
        habit = self._eligible_habit(db)
        graduate_habit(db, habit.id)
        db.refresh(habit)
        original_graduated_at = habit.graduated_at

        result = graduate_habit(db, habit.id)

        assert result.success is False
        db.refresh(habit)
        assert habit.graduated_at == original_graduated_at

    def test_re_scaffold_clears_graduated_at(self, db):
        """re_scaffold_habit() sets graduated_at back to None."""
        habit = self._eligible_habit(db)
        graduate_habit(db, habit.id)
        db.refresh(habit)
        assert habit.graduated_at is not None

        re_scaffold_habit(db, habit.id)
        db.refresh(habit)
        assert habit.graduated_at is None

    def test_slip_detection_uses_graduated_at_not_updated_at(self, db):
        """days_since_graduation reflects graduated_at, not updated_at."""
        habit = _create_habit(
            db,
            scaffolding_status="graduated",
            notification_frequency="graduated",
            accountable_since=date.today() - timedelta(days=90),
        )
        # Set graduated_at to 20 days ago
        grad_time = datetime.now(tz=UTC) - timedelta(days=20)
        habit.graduated_at = grad_time
        db.commit()
        db.refresh(habit)

        # Add completions so we don't trigger slip signals
        for i in range(5):
            _create_completion(db, habit.id, days_ago=i + 1)

        result = evaluate_graduated_habit_slip(db, habit.id)
        assert result.days_since_graduation == 20

    def test_patch_does_not_affect_days_since_graduation(self, db):
        """Editing a graduated habit's description does not reset days_since_graduation."""
        habit = _create_habit(
            db,
            scaffolding_status="graduated",
            notification_frequency="graduated",
            accountable_since=date.today() - timedelta(days=90),
        )
        # Graduate 15 days ago
        grad_time = datetime.now(tz=UTC) - timedelta(days=15)
        habit.graduated_at = grad_time
        db.commit()
        db.refresh(habit)

        # Simulate a PATCH — change description, which triggers updated_at change
        habit.description = "Updated description after graduation"
        db.commit()
        db.refresh(habit)

        # Add completions so we don't trigger slip signals
        for i in range(5):
            _create_completion(db, habit.id, days_ago=i + 1)

        result = evaluate_graduated_habit_slip(db, habit.id)
        assert result.days_since_graduation == 15

    def test_graduated_at_null_falls_back_to_zero(self, db):
        """If graduated_at is None (legacy data), days_since_graduation is 0."""
        habit = _create_habit(
            db,
            scaffolding_status="graduated",
            notification_frequency="graduated",
            accountable_since=date.today() - timedelta(days=90),
        )
        # graduated_at is None by default (no migration backfill)
        assert habit.graduated_at is None

        for i in range(5):
            _create_completion(db, habit.id, days_ago=i + 1)

        result = evaluate_graduated_habit_slip(db, habit.id)
        assert result.days_since_graduation == 0

    def test_graduated_at_in_response_schema(self, db):
        """HabitResponse includes graduated_at field."""
        from app.schemas.habits import HabitResponse

        habit = self._eligible_habit(db)
        graduate_habit(db, habit.id)
        db.refresh(habit)

        response = HabitResponse.model_validate(habit)
        assert response.graduated_at is not None
        assert response.graduated_at == habit.graduated_at

    def test_graduated_at_null_in_response_schema(self, db):
        """HabitResponse shows None for non-graduated habits."""
        from app.schemas.habits import HabitResponse

        habit = _create_habit(db, scaffolding_status="accountable")
        response = HabitResponse.model_validate(habit)
        assert response.graduated_at is None


# ===========================================================================
# [2G-fix-02] position field for routine ordering
# ===========================================================================


class TestHabitPositionField:
    """Tests for the position column added by 2G-fix-02."""

    def test_position_accepted_on_create(self, client):
        """POST /api/habits accepts position field."""
        from tests.conftest import make_habit

        habit = make_habit(client, position=3)
        assert habit["position"] == 3

    def test_position_accepted_on_update(self, client):
        """PATCH /api/habits/{id} accepts position field."""
        from tests.conftest import make_habit

        habit = make_habit(client)
        assert habit["position"] is None

        resp = client.patch(f"/api/habits/{habit['id']}", json={"position": 5})
        assert resp.status_code == 200
        assert resp.json()["position"] == 5

    def test_position_in_response(self, client):
        """HabitResponse includes position field."""
        from tests.conftest import make_habit

        habit = make_habit(client, position=1)
        resp = client.get(f"/api/habits/{habit['id']}")
        assert resp.status_code == 200
        assert resp.json()["position"] == 1

    def test_position_defaults_to_null(self, client):
        """Position is null when not specified."""
        from tests.conftest import make_habit

        habit = make_habit(client)
        assert habit["position"] is None

    def test_tracking_ordered_by_position_then_created_at(self, db):
        """Active tracking habits sorted by position first, then created_at."""
        routine = _create_routine(db)

        # Create habits in reverse position order
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="active",
            title="Position 2",
            position=2,
        )
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="active",
            title="Position 1",
            position=1,
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.suggested_next is not None
        assert result.suggested_next.habit_name == "Position 1"

    def test_null_position_sorts_after_explicit(self, db):
        """Habits with null position sort after habits with explicit positions."""
        routine = _create_routine(db)

        # Null position created first (would win on created_at alone)
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="active",
            title="No Position",
            position=None,
        )
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="active",
            title="Has Position",
            position=10,
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.suggested_next is not None
        assert result.suggested_next.habit_name == "Has Position"

    def test_paused_ordered_by_position_then_accountable_since(self, db):
        """Paused tracking habits sorted by position first, then accountable_since."""
        routine = _create_routine(db)

        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="paused",
            title="Paused Pos 3",
            position=3,
            accountable_since=date.today() - timedelta(days=60),
        )
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="paused",
            title="Paused Pos 1",
            position=1,
            accountable_since=date.today() - timedelta(days=5),
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.suggested_next is not None
        assert result.suggested_next.habit_name == "Paused Pos 1"
        assert result.suggested_next.source == "paused"

    def test_paused_null_position_falls_back_to_accountable_since(self, db):
        """Paused habits with null position fall back to accountable_since ordering."""
        routine = _create_routine(db)

        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="paused",
            title="Newer Paused",
            accountable_since=date.today() - timedelta(days=5),
        )
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="paused",
            title="Older Paused",
            accountable_since=date.today() - timedelta(days=30),
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.suggested_next is not None
        assert result.suggested_next.habit_name == "Older Paused"

    def test_created_at_fallback_when_all_positions_null(self, db):
        """With no position set, falls back to created_at ordering."""
        routine = _create_routine(db)

        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="active",
            title="First Created",
        )
        _create_habit(
            db,
            routine_id=routine.id,
            scaffolding_status="tracking",
            status="active",
            title="Second Created",
        )

        result = get_stacking_recommendation(db, routine.id)

        assert result.suggested_next is not None
        assert result.suggested_next.habit_name == "First Created"


# ===========================================================================
# [2A-Bug-03] D1 regression — scalar defaults removed on graduation override
# columns; NULL-means-inherit; friction-aware resolver fires end-to-end.
#
# Also covers Packet 5 Finding #8 Observation 1 absorption: a never-overridden
# accountable habit must return graduation_params.source == "friction_default"
# from GET /api/habits/{id}/graduation-status. Pre-D1 the scalar defaults made
# the friction_default branch unreachable — every habit was labeled per_habit.
# ===========================================================================


class TestGraduationOverrideDefaultsD1:

    def test_post_habit_without_overrides_creates_null_columns(self, client):
        """New habit with no override payload has NULL in all three columns."""
        resp = client.post(
            "/api/habits",
            json={"title": "Friction 3", "frequency": "daily", "friction_score": 3},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["graduation_window"] is None
        assert body["graduation_target"] is None
        assert body["graduation_threshold"] is None

    def test_friction_3_habit_resolves_to_friction_3_defaults(self, client):
        """Friction-3 habit without overrides resolves to (45, 0.85, 45)."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Friction 3",
                "frequency": "daily",
                "friction_score": 3,
                "scaffolding_status": "accountable",
                "accountable_since": date.today().isoformat(),
            },
        )
        habit_id = resp.json()["id"]

        status = client.get(f"/api/habits/{habit_id}/graduation-status")
        assert status.status_code == 200
        params = status.json()["graduation_params"]
        assert params["window_days"] == 45
        assert params["target_rate"] == 0.85
        assert params["threshold_days"] == 45

    def test_friction_4_habit_resolves_to_friction_4_defaults(self, client):
        """Friction-4 habit without overrides resolves to (60, 0.80, 60)."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Friction 4",
                "frequency": "daily",
                "friction_score": 4,
                "scaffolding_status": "accountable",
                "accountable_since": date.today().isoformat(),
            },
        )
        habit_id = resp.json()["id"]

        status = client.get(f"/api/habits/{habit_id}/graduation-status")
        params = status.json()["graduation_params"]
        assert params["window_days"] == 60
        assert params["target_rate"] == 0.80
        assert params["threshold_days"] == 60

    def test_friction_5_habit_resolves_to_friction_5_defaults(self, client):
        """Friction-5 habit without overrides resolves to (60, 0.80, 60)."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Friction 5",
                "frequency": "daily",
                "friction_score": 5,
                "scaffolding_status": "accountable",
                "accountable_since": date.today().isoformat(),
            },
        )
        habit_id = resp.json()["id"]

        status = client.get(f"/api/habits/{habit_id}/graduation-status")
        params = status.json()["graduation_params"]
        assert params["window_days"] == 60
        assert params["target_rate"] == 0.80
        assert params["threshold_days"] == 60

    def test_friction_1_habit_resolves_to_friction_1_defaults(self, client):
        """Friction-1 habit without overrides resolves to (30, 0.85, 30)."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Friction 1",
                "frequency": "daily",
                "friction_score": 1,
                "scaffolding_status": "accountable",
                "accountable_since": date.today().isoformat(),
            },
        )
        habit_id = resp.json()["id"]

        status = client.get(f"/api/habits/{habit_id}/graduation-status")
        params = status.json()["graduation_params"]
        assert params["window_days"] == 30
        assert params["target_rate"] == 0.85
        assert params["threshold_days"] == 30

    def test_user_override_via_post_is_preserved(self, client, db):
        """POST with explicit graduation_window=50 stores 50 and resolver returns 50."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Override",
                "frequency": "daily",
                "friction_score": 5,  # would resolve to 60 without override
                "graduation_window": 50,
                "scaffolding_status": "accountable",
                "accountable_since": date.today().isoformat(),
            },
        )
        habit_id = resp.json()["id"]
        assert resp.json()["graduation_window"] == 50

        # Column is the override value, not the friction default.
        habit = db.query(Habit).filter(Habit.id == uuid.UUID(habit_id)).one()
        assert habit.graduation_window == 50

        # Other columns remain NULL (unset by caller).
        assert habit.graduation_target is None
        assert habit.graduation_threshold is None

        window, target, threshold = resolve_graduation_params(habit)
        assert window == 50
        assert target == 0.80  # friction-5 default for unset target
        assert threshold == 60  # friction-5 default for unset threshold

    def test_re_scaffold_compounds_against_friction_5_baseline(self, client, db):
        """Friction-5 habit re-scaffolded once evaluates at 75/0.85/75, not 37/0.90/37."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Friction 5",
                "frequency": "daily",
                "friction_score": 5,
                "scaffolding_status": "graduated",
                "notification_frequency": "graduated",
                "accountable_since": date.today().isoformat(),
            },
        )
        habit_id = resp.json()["id"]

        re_scaffold = client.post(f"/api/habits/{habit_id}/re-scaffold")
        assert re_scaffold.status_code == 200

        status = client.get(f"/api/habits/{habit_id}/graduation-status")
        params = status.json()["graduation_params"]
        # 25% tightening on friction-5 baseline: int(60*1.25)=75, min(0.80+0.05, 0.95)≈0.85
        assert params["window_days"] == 75
        assert params["target_rate"] == pytest.approx(0.85)
        assert params["threshold_days"] == 75

    def test_graduation_status_source_is_friction_default_when_no_overrides(self, client):
        """Never-overridden habit labels graduation_params.source = 'friction_default'.

        Absorbs Packet 5 Finding #8 Observation 1. Pre-D1 the scalar defaults
        on the override columns made the any-is-not-None check always True, so
        the friction_default branch at routers/graduation.py:305-309 was
        unreachable. Post-D1 the columns are NULL by default and the branch
        fires correctly.
        """
        resp = client.post(
            "/api/habits",
            json={
                "title": "Un-overridden",
                "frequency": "daily",
                "friction_score": 3,
                "scaffolding_status": "accountable",
                "accountable_since": date.today().isoformat(),
            },
        )
        habit_id = resp.json()["id"]

        status = client.get(f"/api/habits/{habit_id}/graduation-status")
        assert status.status_code == 200
        assert status.json()["graduation_params"]["source"] == "friction_default"

    def test_graduation_status_source_is_per_habit_when_any_override(self, client):
        """Explicitly-overridden habit labels graduation_params.source = 'per_habit'."""
        resp = client.post(
            "/api/habits",
            json={
                "title": "Overridden",
                "frequency": "daily",
                "friction_score": 3,
                "graduation_window": 50,  # single column override is enough
                "scaffolding_status": "accountable",
                "accountable_since": date.today().isoformat(),
            },
        )
        habit_id = resp.json()["id"]

        status = client.get(f"/api/habits/{habit_id}/graduation-status")
        assert status.status_code == 200
        assert status.json()["graduation_params"]["source"] == "per_habit"
