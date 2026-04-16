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

"""SQLAlchemy ORM models for the BRAIN 3.0 seven-pillar data model."""

import uuid
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text

from app.database import Base
from app.schemas.rule import RuleAction, RuleEntityType, RuleMetric, RuleOperator

# ---------------------------------------------------------------------------
# Association table: task_tags
# ---------------------------------------------------------------------------


class TaskTag(Base):
    """Many-to-many link between tasks and tags."""

    __tablename__ = "task_tags"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ActivityTag(Base):
    """Many-to-many link between activity log entries and tags."""

    __tablename__ = "activity_tags"

    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activity_log.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ArtifactTag(Base):
    """Many-to-many link between artifacts and tags."""

    __tablename__ = "artifact_tags"

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ProtocolTag(Base):
    """Many-to-many link between protocols and tags."""

    __tablename__ = "protocol_tags"

    protocol_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("protocols.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


class DirectiveTag(Base):
    """Many-to-many link between directives and tags."""

    __tablename__ = "directive_tags"

    directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("directives.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


# ---------------------------------------------------------------------------
# Association tables: skill relationships
# ---------------------------------------------------------------------------


class SkillDomain(Base):
    """Many-to-many link between skills and domains."""

    __tablename__ = "skill_domains"

    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    )
    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id", ondelete="CASCADE"),
        primary_key=True,
    )


class SkillProtocol(Base):
    """Many-to-many link between skills and protocols."""

    __tablename__ = "skill_protocols"

    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    )
    protocol_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("protocols.id", ondelete="CASCADE"),
        primary_key=True,
    )


class SkillDirective(Base):
    """Many-to-many link between skills and directives."""

    __tablename__ = "skill_directives"

    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    )
    directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("directives.id", ondelete="CASCADE"),
        primary_key=True,
    )


# ---------------------------------------------------------------------------
# Pillar 1: Domains
# ---------------------------------------------------------------------------


class Domain(Base):
    """Top-level life area (House, Network, Finances, Health, etc.)."""

    __tablename__ = "domains"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String)
    sort_order: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    goals: Mapped[list["Goal"]] = relationship(
        back_populates="domain",
        cascade="all, delete-orphan",
    )
    routines: Mapped[list["Routine"]] = relationship(
        back_populates="domain",
        cascade="all, delete-orphan",
    )
    skills: Mapped[list["Skill"]] = relationship(
        secondary="skill_domains",
        back_populates="domains",
    )


# ---------------------------------------------------------------------------
# Pillar 2: Goals
# ---------------------------------------------------------------------------


class Goal(Base):
    """Desired outcome tied to a domain."""

    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'paused', 'achieved', 'abandoned')",
            name="ck_goals_status",
        ),
    )

    # Relationships
    domain: Mapped["Domain"] = relationship(back_populates="goals")
    projects: Mapped[list["Project"]] = relationship(
        back_populates="goal",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# Pillar 3: Projects
# ---------------------------------------------------------------------------


class Project(Base):
    """Concrete initiative that advances a goal."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("goals.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="not_started")
    deadline: Mapped[date | None] = mapped_column(Date)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('not_started', 'active', 'blocked', 'completed', 'abandoned')",
            name="ck_projects_status",
        ),
        CheckConstraint(
            "progress_pct >= 0 AND progress_pct <= 100",
            name="ck_projects_progress_pct",
        ),
    )

    # Relationships
    goal: Mapped["Goal"] = relationship(back_populates="projects")
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# Pillar 4: Tasks
# ---------------------------------------------------------------------------


class Task(Base):
    """Actionable item, optionally tied to a project."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    cognitive_type: Mapped[str | None] = mapped_column(String)
    energy_cost: Mapped[int | None] = mapped_column(Integer)
    activation_friction: Mapped[int | None] = mapped_column(Integer)
    context_required: Mapped[str | None] = mapped_column(String)
    due_date: Mapped[date | None] = mapped_column(Date)
    recurrence_rule: Mapped[str | None] = mapped_column(String)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'completed', 'skipped', 'deferred')",
            name="ck_tasks_status",
        ),
        CheckConstraint(
            "cognitive_type IN ("
            "'hands_on', 'communication', 'decision', 'errand', 'admin', 'focus_work'"
            ") OR cognitive_type IS NULL",
            name="ck_tasks_cognitive_type",
        ),
        CheckConstraint(
            "energy_cost BETWEEN 1 AND 5 OR energy_cost IS NULL",
            name="ck_tasks_energy_cost",
        ),
        CheckConstraint(
            "activation_friction BETWEEN 1 AND 5 OR activation_friction IS NULL",
            name="ck_tasks_activation_friction",
        ),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_cognitive_type", "cognitive_type"),
        Index("ix_tasks_energy_cost", "energy_cost"),
    )

    # Relationships
    project: Mapped["Project | None"] = relationship(back_populates="tasks")
    tags: Mapped[list["Tag"]] = relationship(
        secondary="task_tags",
        back_populates="tasks",
    )
    activity_logs: Mapped[list["ActivityLog"]] = relationship(back_populates="task")


# ---------------------------------------------------------------------------
# Pillar 5: Tags
# ---------------------------------------------------------------------------


class Tag(Base):
    """Lightweight label for cross-cutting task categorisation."""

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String)

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(
        secondary="task_tags",
        back_populates="tags",
    )
    activity_logs: Mapped[list["ActivityLog"]] = relationship(
        secondary="activity_tags",
        back_populates="tags",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        secondary="artifact_tags",
        back_populates="tags",
    )
    protocols: Mapped[list["Protocol"]] = relationship(
        secondary="protocol_tags",
        back_populates="tags",
    )
    directives: Mapped[list["Directive"]] = relationship(
        secondary="directive_tags",
        back_populates="tags",
    )


# ---------------------------------------------------------------------------
# Pillar 6: Routines & Schedule
# ---------------------------------------------------------------------------


class Routine(Base):
    """Recurring habit tied to a domain."""

    __tablename__ = "routines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    frequency: Mapped[str] = mapped_column(String, nullable=False)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_completed: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    energy_cost: Mapped[int | None] = mapped_column(Integer)
    activation_friction: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "frequency IN ('daily', 'weekdays', 'weekends', 'weekly', 'custom')",
            name="ck_routines_frequency",
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'retired')",
            name="ck_routines_status",
        ),
        CheckConstraint(
            "energy_cost BETWEEN 1 AND 5 OR energy_cost IS NULL",
            name="ck_routines_energy_cost",
        ),
        CheckConstraint(
            "activation_friction BETWEEN 1 AND 5 OR activation_friction IS NULL",
            name="ck_routines_activation_friction",
        ),
        Index("ix_routines_status", "status"),
    )

    # Relationships
    domain: Mapped["Domain"] = relationship(back_populates="routines")
    schedules: Mapped[list["RoutineSchedule"]] = relationship(
        back_populates="routine",
        cascade="all, delete-orphan",
    )
    habits: Mapped[list["Habit"]] = relationship(
        back_populates="routine",
        cascade="all, delete-orphan",
    )
    completions: Mapped[list["RoutineCompletion"]] = relationship(
        back_populates="routine",
        cascade="all, delete-orphan",
    )
    activity_logs: Mapped[list["ActivityLog"]] = relationship(back_populates="routine")


class RoutineSchedule(Base):
    """When a routine should occur (day/time preferences)."""

    __tablename__ = "routine_schedule"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    routine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routines.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_of_week: Mapped[str | None] = mapped_column(String)
    time_of_day: Mapped[str | None] = mapped_column(String)
    preferred_window: Mapped[str | None] = mapped_column(String)

    # Relationships
    routine: Mapped["Routine"] = relationship(back_populates="schedules")


# ---------------------------------------------------------------------------
# Habits — atomic behavioral units (standalone or under a routine)
# ---------------------------------------------------------------------------


class Habit(Base):
    """Atomic behavioral unit that can exist standalone or nested under a routine."""

    __tablename__ = "habits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    routine_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routines.id", ondelete="CASCADE"),
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="active",
    )
    frequency: Mapped[str | None] = mapped_column(String)
    notification_frequency: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="none",
    )
    scaffolding_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="tracking",
    )
    introduced_at: Mapped[date | None] = mapped_column(Date)
    graduation_window: Mapped[int | None] = mapped_column(Integer, default=30)
    graduation_target: Mapped[float | None] = mapped_column(
        Numeric(precision=3, scale=2),
        default=0.85,
    )
    graduation_threshold: Mapped[int | None] = mapped_column(Integer, default=30)
    friction_score: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[int | None] = mapped_column(Integer)
    re_scaffold_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    last_frequency_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    graduated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    current_streak: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    best_streak: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    last_completed: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'paused', 'graduated', 'abandoned')",
            name="ck_habits_status",
        ),
        CheckConstraint(
            "frequency IN ('daily', 'weekdays', 'weekends', 'weekly', 'custom') "
            "OR frequency IS NULL",
            name="ck_habits_frequency",
        ),
        CheckConstraint(
            "notification_frequency IN ("
            "'daily', 'every_other_day', 'twice_week', 'weekly', 'graduated', 'none')",
            name="ck_habits_notification_frequency",
        ),
        CheckConstraint(
            "scaffolding_status IN ('tracking', 'accountable', 'graduated')",
            name="ck_habits_scaffolding_status",
        ),
        CheckConstraint(
            "friction_score IS NULL OR (friction_score >= 1 AND friction_score <= 5)",
            name="ck_habits_friction_score",
        ),
        Index("ix_habits_status", "status"),
        Index("ix_habits_routine_id", "routine_id"),
    )

    # Relationships
    routine: Mapped["Routine | None"] = relationship(back_populates="habits")
    completions: Mapped[list["HabitCompletion"]] = relationship(
        back_populates="habit",
        cascade="all, delete-orphan",
    )
    activity_logs: Mapped[list["ActivityLog"]] = relationship(back_populates="habit")


# ---------------------------------------------------------------------------
# Habit Completions — per-event completion records
# ---------------------------------------------------------------------------


class HabitCompletion(Base):
    """Record of a single habit completion event."""

    __tablename__ = "habit_completions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    habit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("habits.id", ondelete="CASCADE"),
        nullable=False,
    )
    completed_at: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "habit_id",
            "completed_at",
            name="uq_habit_completions_habit_date",
        ),
        CheckConstraint(
            "source IN ('individual', 'routine_cascade', 'reconciliation')",
            name="ck_habit_completions_source",
        ),
    )

    # Relationships
    habit: Mapped["Habit"] = relationship(back_populates="completions")


# ---------------------------------------------------------------------------
# Routine Completions — per-event routine completion records
# ---------------------------------------------------------------------------


class RoutineCompletion(Base):
    """Record of a single routine completion event."""

    __tablename__ = "routine_completions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    routine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routines.id", ondelete="CASCADE"),
        nullable=False,
    )
    completed_at: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    freeform_note: Mapped[str | None] = mapped_column(Text)
    reconciled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    reconciled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('all_done', 'partial', 'skipped')",
            name="ck_routine_completions_status",
        ),
        Index(
            "ix_routine_completions_routine_completed",
            "routine_id",
            "completed_at",
        ),
        Index("ix_routine_completions_reconciled", "reconciled"),
    )

    # Relationships
    routine: Mapped["Routine"] = relationship(back_populates="completions")


# ---------------------------------------------------------------------------
# Pillar 7a: State Check-ins
# ---------------------------------------------------------------------------


class StateCheckin(Base):
    """Point-in-time self-assessment of energy, mood, and focus."""

    __tablename__ = "state_checkins"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    checkin_type: Mapped[str] = mapped_column(String, nullable=False)
    energy_level: Mapped[int | None] = mapped_column(Integer)
    mood: Mapped[int | None] = mapped_column(Integer)
    focus_level: Mapped[int | None] = mapped_column(Integer)
    freeform_note: Mapped[str | None] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(String)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "checkin_type IN ('morning', 'midday', 'evening', 'micro', 'freeform')",
            name="ck_state_checkins_type",
        ),
        CheckConstraint(
            "energy_level BETWEEN 1 AND 5 OR energy_level IS NULL",
            name="ck_state_checkins_energy_level",
        ),
        CheckConstraint(
            "mood BETWEEN 1 AND 5 OR mood IS NULL",
            name="ck_state_checkins_mood",
        ),
        CheckConstraint(
            "focus_level BETWEEN 1 AND 5 OR focus_level IS NULL",
            name="ck_state_checkins_focus_level",
        ),
    )

    # Relationships
    activity_logs: Mapped[list["ActivityLog"]] = relationship(back_populates="checkin")


# ---------------------------------------------------------------------------
# Pillar 7b: Activity Log
# ---------------------------------------------------------------------------


class ActivityLog(Base):
    """Record of an action taken — completed task, skipped routine, check-in, etc."""

    __tablename__ = "activity_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
    )
    routine_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routines.id", ondelete="SET NULL"),
    )
    checkin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("state_checkins.id", ondelete="SET NULL"),
    )
    habit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("habits.id", ondelete="SET NULL"),
    )
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    energy_before: Mapped[int | None] = mapped_column(Integer)
    energy_after: Mapped[int | None] = mapped_column(Integer)
    mood_rating: Mapped[int | None] = mapped_column(Integer)
    friction_actual: Mapped[int | None] = mapped_column(Integer)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "action_type IN ("
            "'completed', 'skipped', 'deferred', 'started', 'reflected', 'checked_in'"
            ")",
            name="ck_activity_log_action_type",
        ),
        CheckConstraint(
            "energy_before BETWEEN 1 AND 5 OR energy_before IS NULL",
            name="ck_activity_log_energy_before",
        ),
        CheckConstraint(
            "energy_after BETWEEN 1 AND 5 OR energy_after IS NULL",
            name="ck_activity_log_energy_after",
        ),
        CheckConstraint(
            "mood_rating BETWEEN 1 AND 5 OR mood_rating IS NULL",
            name="ck_activity_log_mood_rating",
        ),
        CheckConstraint(
            "friction_actual BETWEEN 1 AND 5 OR friction_actual IS NULL",
            name="ck_activity_log_friction_actual",
        ),
        Index("ix_activity_log_logged_at", "logged_at"),
    )

    # Relationships
    task: Mapped["Task | None"] = relationship(back_populates="activity_logs")
    routine: Mapped["Routine | None"] = relationship(back_populates="activity_logs")
    checkin: Mapped["StateCheckin | None"] = relationship(back_populates="activity_logs")
    habit: Mapped["Habit | None"] = relationship(back_populates="activity_logs")
    tags: Mapped[list["Tag"]] = relationship(
        secondary="activity_tags",
        back_populates="activity_logs",
    )


# ---------------------------------------------------------------------------
# Artifacts — living reference documents
# ---------------------------------------------------------------------------


class Artifact(Base):
    """Stored document with versioning, multi-part grouping, and tagging."""

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    content_size: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
    )
    is_seedable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "artifact_type IN ("
            "'document', 'protocol', 'brief', 'prompt', 'template', 'journal', 'spec'"
            ")",
            name="ck_artifacts_artifact_type",
        ),
        CheckConstraint(
            "octet_length(content) <= 524288",
            name="ck_artifacts_content_size",
        ),
        Index("ix_artifacts_artifact_type", "artifact_type"),
        Index("ix_artifacts_is_seedable", "is_seedable"),
    )

    # Relationships
    tags: Mapped[list["Tag"]] = relationship(
        secondary="artifact_tags",
        back_populates="artifacts",
    )
    parent: Mapped["Artifact | None"] = relationship(
        remote_side=[id],
        foreign_keys=[parent_id],
    )
    children: Mapped[list["Artifact"]] = relationship(
        foreign_keys=[parent_id],
        overlaps="parent",
    )
    protocols: Mapped[list["Protocol"]] = relationship(back_populates="artifact")
    skills: Mapped[list["Skill"]] = relationship(back_populates="artifact")


# ---------------------------------------------------------------------------
# Protocols — step-by-step procedures
# ---------------------------------------------------------------------------


class Protocol(Base):
    """Repeatable behavioral pattern with ordered steps (JSONB)."""

    __tablename__ = "protocols"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
    )
    is_seedable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (Index("ix_protocols_is_seedable", "is_seedable"),)

    # Relationships
    tags: Mapped[list["Tag"]] = relationship(
        secondary="protocol_tags",
        back_populates="protocols",
    )
    artifact: Mapped["Artifact | None"] = relationship(back_populates="protocols")
    skills: Mapped[list["Skill"]] = relationship(
        secondary="skill_protocols",
        back_populates="protocols",
    )


# ---------------------------------------------------------------------------
# Directives — principles and guardrails
# ---------------------------------------------------------------------------


class Directive(Base):
    """Declarative rule or guardrail with scope-based resolution."""

    __tablename__ = "directives"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    scope_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    is_seedable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "scope IN ('global', 'skill', 'agent')",
            name="ck_directives_scope",
        ),
        CheckConstraint(
            "priority BETWEEN 1 AND 10",
            name="ck_directives_priority",
        ),
        Index("ix_directives_scope", "scope"),
        Index("ix_directives_priority", "priority"),
    )

    # Relationships
    tags: Mapped[list["Tag"]] = relationship(
        secondary="directive_tags",
        back_populates="directives",
    )
    skills: Mapped[list["Skill"]] = relationship(
        secondary="skill_directives",
        back_populates="directives",
    )


# ---------------------------------------------------------------------------
# Skills — contextual operating modes
# ---------------------------------------------------------------------------


class Skill(Base):
    """Contextual mode that composes protocols, directives, and domains."""

    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    adhd_patterns: Mapped[str | None] = mapped_column(Text)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
    )
    is_seedable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_skills_is_seedable", "is_seedable"),
        Index("ix_skills_is_default", "is_default"),
    )

    # Relationships
    domains: Mapped[list["Domain"]] = relationship(
        secondary="skill_domains",
        back_populates="skills",
    )
    protocols: Mapped[list["Protocol"]] = relationship(
        secondary="skill_protocols",
        back_populates="skills",
    )
    directives: Mapped[list["Directive"]] = relationship(
        secondary="skill_directives",
        back_populates="skills",
    )
    artifact: Mapped["Artifact | None"] = relationship(back_populates="skills")


# ---------------------------------------------------------------------------
# Notification Queue — proactive notification system
# ---------------------------------------------------------------------------


class NotificationQueue(Base):
    """Queued notification awaiting delivery and optional user response."""

    __tablename__ = "notification_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    notification_type: Mapped[str] = mapped_column(String, nullable=False)
    delivery_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="notification",
    )
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="pending",
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    target_entity_type: Mapped[str] = mapped_column(String, nullable=False)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    canned_responses: Mapped[list | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
    )
    response: Mapped[str | None] = mapped_column(String)
    response_note: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    scheduled_by: Mapped[str] = mapped_column(String, nullable=False)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rules.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "notification_type IN ("
            "'habit_nudge', 'routine_checklist', 'checkin_prompt', "
            "'time_block_reminder', 'deadline_event_alert', "
            "'pattern_observation', 'stale_work_nudge'"
            ")",
            name="ck_notification_queue_notification_type",
        ),
        CheckConstraint(
            "delivery_type IN ('notification')",
            name="ck_notification_queue_delivery_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'delivered', 'responded', 'expired')",
            name="ck_notification_queue_status",
        ),
        CheckConstraint(
            "scheduled_by IN ('system', 'claude', 'rule')",
            name="ck_notification_queue_scheduled_by",
        ),
        Index("ix_nq_scheduler_poll", "status", "scheduled_at"),
        Index("ix_nq_expiry_check", "status", "expires_at"),
        Index("ix_nq_target_lookup", "target_entity_type", "target_entity_id"),
        Index("ix_nq_rule_traceability", "rule_id"),
        Index("ix_nq_type_filter", "notification_type"),
        Index("ix_nq_scheduled_by", "scheduled_by"),
    )


# ---------------------------------------------------------------------------
# Rules Engine — conditional logic layer for automated notifications
# ---------------------------------------------------------------------------


class Rule(Base):
    """A rule that watches an entity metric and fires a notification."""

    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[RuleEntityType] = mapped_column(
        SAEnum(RuleEntityType, native_enum=False),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    metric: Mapped[RuleMetric] = mapped_column(
        SAEnum(RuleMetric, native_enum=False),
        nullable=False,
    )
    operator: Mapped[RuleOperator] = mapped_column(
        SAEnum(RuleOperator, native_enum=False),
        nullable=False,
    )
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[RuleAction] = mapped_column(
        SAEnum(RuleAction, native_enum=False),
        nullable=False,
        server_default="create_notification",
    )
    notification_type: Mapped[str] = mapped_column(String, nullable=False)
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    cooldown_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("24"),
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "notification_type IN ("
            "'habit_nudge', 'routine_checklist', 'checkin_prompt', "
            "'time_block_reminder', 'deadline_event_alert', "
            "'pattern_observation', 'stale_work_nudge'"
            ")",
            name="ck_rules_notification_type",
        ),
        UniqueConstraint("name", name="uq_rules_name"),
        Index("ix_rules_entity_lookup", "entity_type", "enabled"),
        Index("ix_rules_entity_scoped", "entity_type", "entity_id"),
    )
