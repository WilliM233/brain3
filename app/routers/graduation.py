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

"""Graduation API endpoints — thin wrappers over the graduation service layer.

Habit-scoped endpoints (evaluate-graduation, graduate, evaluate-frequency,
step-down-frequency, evaluate-slip, re-scaffold, graduation-status) are
mounted under /api/habits/{habit_id}/... via habit_graduation_router.

Graduation-scoped endpoints (suggest-next, evaluate-all-slips) are mounted
under /api/graduation/... via graduation_router.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Habit
from app.services.graduation import (
    FrequencyChangeResult,
    FrequencyStepResult,
    GraduationExecutionResult,
    GraduationResult,
    ReScaffoldResult,
    SlipDetectionResult,
    StackingRecommendation,
    apply_frequency_step_down,
    evaluate_all_graduated_habits,
    evaluate_frequency_step_down,
    evaluate_graduated_habit_slip,
    evaluate_graduation,
    get_stacking_recommendation,
    graduate_habit,
    re_scaffold_habit,
)
from app.services.graduation_defaults import resolve_graduation_params

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Mounted at /api/habits in main.py (alongside existing habits router)
habit_graduation_router = APIRouter()

# Mounted at /api/graduation in main.py
graduation_router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class GraduateRequest(BaseModel):
    """Request body for the graduate endpoint."""
    force: bool = False


class GraduationStatusResponse(BaseModel):
    """Composite graduation status for dashboard display."""
    habit_id: UUID
    habit_name: str
    scaffolding_status: str
    notification_frequency: str
    friction_score: int | None
    re_scaffold_count: int
    accountable_since: str | None
    days_accountable: int
    graduation_params: dict
    current_metrics: dict
    progress_summary: str
    frequency_step_down: dict


class BatchSlipResponse(BaseModel):
    """Response from batch slip evaluation."""
    evaluated_count: int
    attention_needed: list[SlipDetectionResult]


# ---------------------------------------------------------------------------
# Helper — resolve habit or 404
# ---------------------------------------------------------------------------

def _get_habit_or_404(db: Session, habit_id: UUID) -> Habit:
    """Fetch a habit by ID or raise 404."""
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    return habit


# ---------------------------------------------------------------------------
# 1. POST /api/habits/{habit_id}/evaluate-graduation
# ---------------------------------------------------------------------------

@habit_graduation_router.post(
    "/{habit_id}/evaluate-graduation",
    response_model=GraduationResult,
)
def evaluate_graduation_endpoint(
    habit_id: UUID, db: Session = Depends(get_db),
) -> GraduationResult:
    """Dry-run graduation evaluation. Returns eligibility metrics without changing state."""
    _get_habit_or_404(db, habit_id)
    return evaluate_graduation(db, habit_id)


# ---------------------------------------------------------------------------
# 2. POST /api/habits/{habit_id}/graduate
# ---------------------------------------------------------------------------

@habit_graduation_router.post(
    "/{habit_id}/graduate",
    response_model=GraduationExecutionResult,
)
def graduate_habit_endpoint(
    habit_id: UUID,
    payload: GraduateRequest | None = None,
    db: Session = Depends(get_db),
) -> GraduationExecutionResult:
    """Execute graduation. Optionally force-graduate."""
    habit = _get_habit_or_404(db, habit_id)

    force = payload.force if payload else False

    # Already graduated — 409
    if habit.scaffolding_status == "graduated":
        raise HTTPException(
            status_code=409,
            detail="Habit is already graduated",
        )

    # Status preconditions — 422
    if habit.status != "active":
        raise HTTPException(
            status_code=422,
            detail=f"Habit status is '{habit.status}', must be 'active'",
        )
    if habit.scaffolding_status != "accountable":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Habit scaffolding_status is '{habit.scaffolding_status}', "
                "must be 'accountable'"
            ),
        )

    result = graduate_habit(db, habit_id, force=force)

    # If the service returned success=False (not eligible, force=False), return 422
    if not result.success and not force:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Habit is not eligible for graduation",
                "evaluation": (
                    result.evaluation.model_dump(mode="json")
                    if result.evaluation else None
                ),
            },
        )

    return result


# ---------------------------------------------------------------------------
# 3. POST /api/habits/{habit_id}/evaluate-frequency
# ---------------------------------------------------------------------------

@habit_graduation_router.post(
    "/{habit_id}/evaluate-frequency",
    response_model=FrequencyStepResult,
)
def evaluate_frequency_endpoint(
    habit_id: UUID, db: Session = Depends(get_db),
) -> FrequencyStepResult:
    """Check if a habit should step down its notification frequency. Read-only."""
    _get_habit_or_404(db, habit_id)
    return evaluate_frequency_step_down(db, habit_id)


# ---------------------------------------------------------------------------
# 4. POST /api/habits/{habit_id}/step-down-frequency
# ---------------------------------------------------------------------------

@habit_graduation_router.post(
    "/{habit_id}/step-down-frequency",
    response_model=FrequencyChangeResult,
)
def step_down_frequency_endpoint(
    habit_id: UUID, db: Session = Depends(get_db),
) -> FrequencyChangeResult:
    """Apply a one-level frequency reduction. Validates recommendation first."""
    _get_habit_or_404(db, habit_id)

    # Evaluate first
    eval_result = evaluate_frequency_step_down(db, habit_id)
    if not eval_result.recommend_step_down:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Step-down not recommended",
                "evaluation": eval_result.model_dump(mode="json"),
            },
        )

    return apply_frequency_step_down(db, habit_id, eval_result.recommended_frequency)


# ---------------------------------------------------------------------------
# 5. POST /api/habits/{habit_id}/evaluate-slip
# ---------------------------------------------------------------------------

@habit_graduation_router.post(
    "/{habit_id}/evaluate-slip",
    response_model=SlipDetectionResult,
)
def evaluate_slip_endpoint(
    habit_id: UUID, db: Session = Depends(get_db),
) -> SlipDetectionResult:
    """Check if a graduated habit shows signs of regression. Read-only."""
    _get_habit_or_404(db, habit_id)
    return evaluate_graduated_habit_slip(db, habit_id)


# ---------------------------------------------------------------------------
# 6. POST /api/habits/{habit_id}/re-scaffold
# ---------------------------------------------------------------------------

@habit_graduation_router.post(
    "/{habit_id}/re-scaffold",
    response_model=ReScaffoldResult,
)
def re_scaffold_endpoint(
    habit_id: UUID, db: Session = Depends(get_db),
) -> ReScaffoldResult:
    """Reverse graduation and return a habit to daily accountability."""
    habit = _get_habit_or_404(db, habit_id)

    if habit.scaffolding_status != "graduated":
        raise HTTPException(
            status_code=422,
            detail=f"Habit scaffolding_status is '{habit.scaffolding_status}', must be 'graduated'",
        )

    return re_scaffold_habit(db, habit_id)


# ---------------------------------------------------------------------------
# 7. GET /api/habits/{habit_id}/graduation-status
# ---------------------------------------------------------------------------

@habit_graduation_router.get(
    "/{habit_id}/graduation-status",
    response_model=GraduationStatusResponse,
)
def graduation_status_endpoint(
    habit_id: UUID, db: Session = Depends(get_db),
) -> dict:
    """User-facing dashboard data. Composites evaluation + frequency data."""
    habit = _get_habit_or_404(db, habit_id)

    # Resolve graduation params
    from app.services.graduation import apply_re_scaffold_tightening

    window, target, threshold = resolve_graduation_params(habit)
    source = "per_habit" if any([
        habit.graduation_window is not None,
        habit.graduation_target is not None,
        habit.graduation_threshold is not None,
    ]) else "friction_default"

    if habit.re_scaffold_count > 0:
        window, target, threshold = apply_re_scaffold_tightening(
            window, target, threshold, habit.re_scaffold_count,
        )

    # Days accountable (days since tracking → accountable transition)
    from datetime import UTC, datetime
    now = datetime.now(tz=UTC)
    if habit.accountable_since is not None:
        days_accountable = (now.date() - habit.accountable_since).days
    else:
        days_accountable = 0

    # Current metrics — only if accountable
    current_rate = 0.0
    total_notifications = 0
    already_done_count = 0
    if habit.scaffolding_status == "accountable":
        try:
            grad_result = evaluate_graduation(db, habit_id)
            current_rate = grad_result.current_rate
            total_notifications = grad_result.total_notifications
            already_done_count = grad_result.already_done_count
        except ValueError:
            pass

    # Build progress summary
    if habit.scaffolding_status == "graduated":
        progress_summary = "Habit has graduated."
    elif habit.scaffolding_status == "tracking":
        progress_summary = "Habit is in tracking mode. Not yet in accountability loop."
    else:
        rate_pct = int(current_rate * 100)
        target_pct = int(target * 100)
        remaining_days = max(0, threshold - days_accountable)
        if remaining_days > 0:
            progress_summary = (
                f"{rate_pct}% of the way to graduation target ({target_pct}%). "
                f"{remaining_days} more days until minimum threshold met."
            )
        elif current_rate >= target:
            progress_summary = (
                f"Meeting graduation target ({rate_pct}% >= {target_pct}%). "
                f"Ready for graduation evaluation."
            )
        else:
            progress_summary = (
                f"{rate_pct}% of the way to graduation target ({target_pct}%). "
                f"Minimum time threshold met."
            )

    # Frequency step-down info
    freq_eligible = False
    freq_recommended = None
    freq_rate = 0.0
    if habit.scaffolding_status == "accountable":
        try:
            freq_result = evaluate_frequency_step_down(db, habit_id)
            freq_eligible = freq_result.recommend_step_down
            freq_recommended = freq_result.recommended_frequency
            freq_rate = freq_result.current_rate
        except ValueError:
            pass

    return {
        "habit_id": habit.id,
        "habit_name": habit.title,
        "scaffolding_status": habit.scaffolding_status,
        "notification_frequency": habit.notification_frequency,
        "friction_score": habit.friction_score,
        "re_scaffold_count": habit.re_scaffold_count,
        "accountable_since": (
            str(habit.accountable_since) if habit.accountable_since else None
        ),
        "days_accountable": days_accountable,
        "graduation_params": {
            "window_days": window,
            "target_rate": target,
            "threshold_days": threshold,
            "source": source,
        },
        "current_metrics": {
            "already_done_rate": current_rate,
            "total_notifications": total_notifications,
            "already_done_count": already_done_count,
        },
        "progress_summary": progress_summary,
        "frequency_step_down": {
            "eligible": freq_eligible,
            "recommended_frequency": freq_recommended,
            "current_rate_over_recent": freq_rate,
        },
    }


# ---------------------------------------------------------------------------
# 8. GET /api/graduation/suggest-next?routine_id={routine_id}
# ---------------------------------------------------------------------------

@graduation_router.get(
    "/suggest-next",
    response_model=StackingRecommendation,
)
def suggest_next_endpoint(
    routine_id: UUID = Query(..., description="The routine to evaluate"),
    db: Session = Depends(get_db),
) -> StackingRecommendation:
    """Check if a routine is ready for a new habit and suggest what to introduce."""
    return get_stacking_recommendation(db, routine_id)


# ---------------------------------------------------------------------------
# 9. POST /api/graduation/evaluate-all-slips
# ---------------------------------------------------------------------------

@graduation_router.post(
    "/evaluate-all-slips",
    response_model=BatchSlipResponse,
)
def evaluate_all_slips_endpoint(
    db: Session = Depends(get_db),
) -> dict:
    """Scheduler endpoint. Evaluates all graduated habits for slip signals."""
    results = evaluate_all_graduated_habits(db)
    # The service already filters to only attention-needed results
    all_graduated = (
        db.query(Habit)
        .filter(Habit.scaffolding_status == "graduated", Habit.status == "active")
        .count()
    )
    return {
        "evaluated_count": all_graduated,
        "attention_needed": results,
    }
