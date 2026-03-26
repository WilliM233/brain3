"""Read-only aggregation and pattern-recognition endpoints."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    ActivityLog,
    Domain,
    Goal,
    Project,
    Routine,
    RoutineSchedule,
    Task,
)
from app.schemas.reports import (
    ActivitySummaryResponse,
    DomainBalanceResponse,
    FrictionAnalysisResponse,
    RoutineAdherenceResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# 1. Activity Summary
# ---------------------------------------------------------------------------


@router.get("/activity-summary", response_model=ActivitySummaryResponse)
def activity_summary(
    after: datetime = Query(...),
    before: datetime = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregated activity stats for a date range."""
    base = db.query(ActivityLog).filter(
        ActivityLog.logged_at >= after,
        ActivityLog.logged_at <= before,
    )

    entries_count = base.count()

    total_completed = base.filter(ActivityLog.action_type == "completed").count()
    total_skipped = base.filter(ActivityLog.action_type == "skipped").count()
    total_deferred = base.filter(ActivityLog.action_type == "deferred").count()

    duration_sum = base.with_entities(
        func.coalesce(func.sum(ActivityLog.duration_minutes), 0),
    ).scalar()

    # Average energy delta where both before and after are present
    energy_delta = base.filter(
        ActivityLog.energy_before.isnot(None),
        ActivityLog.energy_after.isnot(None),
    ).with_entities(
        func.avg(ActivityLog.energy_after - ActivityLog.energy_before),
    ).scalar()

    avg_mood = base.filter(
        ActivityLog.mood_rating.isnot(None),
    ).with_entities(
        func.avg(ActivityLog.mood_rating),
    ).scalar()

    return {
        "period_start": after,
        "period_end": before,
        "total_completed": total_completed,
        "total_skipped": total_skipped,
        "total_deferred": total_deferred,
        "total_duration_minutes": duration_sum or 0,
        "avg_energy_delta": round(float(energy_delta), 2) if energy_delta is not None else None,
        "avg_mood": round(float(avg_mood), 2) if avg_mood is not None else None,
        "entries_count": entries_count,
    }


# ---------------------------------------------------------------------------
# 2. Domain Balance
# ---------------------------------------------------------------------------


@router.get("/domain-balance", response_model=list[DomainBalanceResponse])
def domain_balance(db: Session = Depends(get_db)) -> list[dict]:
    """Per-domain counts of active items and recency."""
    domains = db.query(Domain).order_by(Domain.sort_order, Domain.name).all()
    today = date.today()
    results = []

    for domain in domains:
        # Active goals
        active_goals = (
            db.query(func.count(Goal.id))
            .filter(Goal.domain_id == domain.id, Goal.status == "active")
            .scalar()
        )

        # Active projects under this domain's goals
        active_projects = (
            db.query(func.count(Project.id))
            .join(Goal, Project.goal_id == Goal.id)
            .filter(Goal.domain_id == domain.id, Project.status == "active")
            .scalar()
        )

        # Pending tasks under this domain's goals → projects
        pending_tasks = (
            db.query(func.count(Task.id))
            .join(Project, Task.project_id == Project.id)
            .join(Goal, Project.goal_id == Goal.id)
            .filter(Goal.domain_id == domain.id, Task.status == "pending")
            .scalar()
        )

        # Overdue tasks
        overdue_tasks = (
            db.query(func.count(Task.id))
            .join(Project, Task.project_id == Project.id)
            .join(Goal, Project.goal_id == Goal.id)
            .filter(
                Goal.domain_id == domain.id,
                Task.due_date < today,
                Task.status.notin_(["completed", "skipped", "abandoned"]),
            )
            .scalar()
        )

        # Days since last activity — via tasks or routines in this domain
        last_task_activity = (
            db.query(func.max(ActivityLog.logged_at))
            .join(Task, ActivityLog.task_id == Task.id)
            .join(Project, Task.project_id == Project.id)
            .join(Goal, Project.goal_id == Goal.id)
            .filter(Goal.domain_id == domain.id)
            .scalar()
        )
        last_routine_activity = (
            db.query(func.max(ActivityLog.logged_at))
            .join(Routine, ActivityLog.routine_id == Routine.id)
            .filter(Routine.domain_id == domain.id)
            .scalar()
        )

        last_activity = None
        for ts in [last_task_activity, last_routine_activity]:
            if ts is not None:
                if last_activity is None or ts > last_activity:
                    last_activity = ts

        days_since = None
        if last_activity is not None:
            if hasattr(last_activity, "date"):
                days_since = (today - last_activity.date()).days
            else:
                days_since = (today - last_activity).days

        results.append({
            "domain_id": domain.id,
            "domain_name": domain.name,
            "active_goals": active_goals,
            "active_projects": active_projects,
            "pending_tasks": pending_tasks,
            "overdue_tasks": overdue_tasks,
            "days_since_last_activity": days_since,
        })

    return results


# ---------------------------------------------------------------------------
# 3. Routine Adherence
# ---------------------------------------------------------------------------


def _count_expected(
    frequency: str,
    start: datetime,
    end: datetime,
    schedules: list[RoutineSchedule] | None = None,
) -> int:
    """Calculate expected completions for a routine in a date range."""
    # Work with dates
    start_date = start.date() if hasattr(start, "date") else start
    end_date = end.date() if hasattr(end, "date") else end
    total_days = (end_date - start_date).days + 1
    if total_days <= 0:
        return 0

    if frequency == "daily":
        return total_days
    elif frequency == "weekdays":
        count = 0
        for i in range(total_days):
            if (start_date + timedelta(days=i)).weekday() < 5:
                count += 1
        return count
    elif frequency == "weekends":
        count = 0
        for i in range(total_days):
            if (start_date + timedelta(days=i)).weekday() >= 5:
                count += 1
        return count
    elif frequency == "weekly":
        return math.ceil(total_days / 7)
    elif frequency == "custom":
        if not schedules:
            return math.ceil(total_days / 7)
        day_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        scheduled_days = {
            day_map[s.day_of_week.lower()]
            for s in schedules
            if s.day_of_week and s.day_of_week.lower() in day_map
        }
        if not scheduled_days:
            return math.ceil(total_days / 7)
        count = 0
        for i in range(total_days):
            if (start_date + timedelta(days=i)).weekday() in scheduled_days:
                count += 1
        return count
    return total_days


@router.get("/routine-adherence", response_model=list[RoutineAdherenceResponse])
def routine_adherence(
    after: datetime = Query(...),
    before: datetime = Query(...),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Per-routine completion rates and streak health."""
    routines = (
        db.query(Routine)
        .filter(Routine.status.in_(["active", "paused"]))
        .all()
    )
    results = []

    for routine in routines:
        completions = (
            db.query(func.count(ActivityLog.id))
            .filter(
                ActivityLog.routine_id == routine.id,
                ActivityLog.action_type == "completed",
                ActivityLog.logged_at >= after,
                ActivityLog.logged_at <= before,
            )
            .scalar()
        )

        schedules = (
            db.query(RoutineSchedule)
            .filter(RoutineSchedule.routine_id == routine.id)
            .all()
        )

        expected = _count_expected(routine.frequency, after, before, schedules)
        adherence = min(completions / expected * 100, 100.0) if expected > 0 else 0.0

        # Get domain name
        domain = db.query(Domain).filter(Domain.id == routine.domain_id).first()

        results.append({
            "routine_id": routine.id,
            "routine_title": routine.title,
            "domain_name": domain.name if domain else "Unknown",
            "frequency": routine.frequency,
            "completions_in_period": completions,
            "expected_in_period": expected,
            "adherence_pct": round(adherence, 1),
            "current_streak": routine.current_streak,
            "best_streak": routine.best_streak,
            "streak_is_broken": routine.current_streak == 0 and routine.status == "active",
        })

    return results


# ---------------------------------------------------------------------------
# 4. Friction Analysis
# ---------------------------------------------------------------------------


@router.get("/friction-analysis", response_model=list[FrictionAnalysisResponse])
def friction_analysis(
    after: datetime | None = Query(None),
    before: datetime | None = Query(None),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Predicted vs actual friction by cognitive type."""
    if after is None:
        after = datetime.now(tz=timezone.utc) - timedelta(days=30)
    if before is None:
        before = datetime.now(tz=timezone.utc)

    # Base query: activity log entries joined to tasks with cognitive_type
    base = (
        db.query(
            Task.cognitive_type,
            ActivityLog.action_type,
            Task.activation_friction,
            ActivityLog.friction_actual,
            Task.energy_cost,
            ActivityLog.energy_before,
            ActivityLog.energy_after,
        )
        .join(Task, ActivityLog.task_id == Task.id)
        .filter(
            ActivityLog.logged_at >= after,
            ActivityLog.logged_at <= before,
            Task.cognitive_type.isnot(None),
        )
        .all()
    )

    # Group by cognitive_type
    groups: dict[str, list] = {}
    for row in base:
        ct = row[0]  # cognitive_type
        if ct not in groups:
            groups[ct] = []
        groups[ct].append(row)

    results = []
    for cognitive_type, rows in sorted(groups.items()):
        friction_predicted = []
        friction_actual = []
        energy_costs = []
        energy_deltas = []
        completed = 0
        skipped = 0
        deferred = 0

        for row in rows:
            action_type = row[1]
            pred_friction = row[2]
            act_friction = row[3]
            energy_cost = row[4]
            energy_before = row[5]
            energy_after = row[6]

            if action_type == "completed":
                completed += 1
            elif action_type == "skipped":
                skipped += 1
            elif action_type == "deferred":
                deferred += 1

            if pred_friction is not None and act_friction is not None:
                friction_predicted.append(pred_friction)
                friction_actual.append(act_friction)

            if energy_cost is not None:
                energy_costs.append(energy_cost)

            if energy_before is not None and energy_after is not None:
                energy_deltas.append(energy_after - energy_before)

        task_count = len(rows)
        total_actions = completed + skipped + deferred
        completion_rate = (completed / total_actions * 100) if total_actions > 0 else 0.0

        avg_pred = sum(friction_predicted) / len(friction_predicted) if friction_predicted else 0.0
        avg_act = sum(friction_actual) / len(friction_actual) if friction_actual else 0.0

        results.append({
            "cognitive_type": cognitive_type,
            "task_count": task_count,
            "avg_predicted_friction": round(avg_pred, 2),
            "avg_actual_friction": round(avg_act, 2),
            "friction_gap": round(avg_pred - avg_act, 2),
            "completion_rate": round(completion_rate, 1),
            "avg_energy_cost": (
                round(sum(energy_costs) / len(energy_costs), 2) if energy_costs else 0.0
            ),
            "avg_energy_delta": (
                round(sum(energy_deltas) / len(energy_deltas), 2) if energy_deltas else None
            ),
        })

    return results
