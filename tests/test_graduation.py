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

from app.models import Habit, NotificationQueue
from app.services.graduation import (
    GraduationResult,
    apply_re_scaffold_tightening,
    evaluate_graduation,
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
