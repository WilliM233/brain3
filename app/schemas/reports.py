"""Pydantic response schemas for reporting and aggregation endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ActivitySummaryResponse(BaseModel):
    """Aggregated activity stats for a date range."""

    period_start: datetime
    period_end: datetime
    total_completed: int
    total_skipped: int
    total_deferred: int
    total_duration_minutes: int
    avg_energy_delta: float | None
    avg_mood: float | None
    entries_count: int


class DomainBalanceResponse(BaseModel):
    """Per-domain counts of active items and recency."""

    domain_id: UUID
    domain_name: str
    active_goals: int
    active_projects: int
    pending_tasks: int
    overdue_tasks: int
    days_since_last_activity: int | None


class RoutineAdherenceResponse(BaseModel):
    """Per-routine completion rates and streak health."""

    routine_id: UUID
    routine_title: str
    domain_name: str
    frequency: str
    completions_in_period: int
    expected_in_period: int
    adherence_pct: float
    current_streak: int
    best_streak: int
    streak_is_broken: bool


class FrictionAnalysisResponse(BaseModel):
    """Predicted vs actual friction by cognitive type."""

    cognitive_type: str
    task_count: int
    avg_predicted_friction: float
    avg_actual_friction: float
    friction_gap: float
    completion_rate: float
    avg_energy_cost: float
    avg_energy_delta: float | None
