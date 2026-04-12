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

"""create habits table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "habits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "routine_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("routines.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("frequency", sa.String(), nullable=True),
        sa.Column(
            "notification_frequency", sa.String(), nullable=False, server_default="none",
        ),
        sa.Column(
            "scaffolding_status", sa.String(), nullable=False, server_default="tracking",
        ),
        sa.Column("introduced_at", sa.Date(), nullable=True),
        sa.Column("graduation_window", sa.Integer(), nullable=True, server_default="30"),
        sa.Column(
            "graduation_target",
            sa.Numeric(precision=3, scale=2),
            nullable=True,
            server_default="0.85",
        ),
        sa.Column(
            "graduation_threshold", sa.Integer(), nullable=True, server_default="30",
        ),
        sa.Column(
            "current_streak", sa.Integer(), nullable=False, server_default=sa.text("0"),
        ),
        sa.Column(
            "best_streak", sa.Integer(), nullable=False, server_default=sa.text("0"),
        ),
        sa.Column("last_completed", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'graduated', 'abandoned')",
            name="ck_habits_status",
        ),
        sa.CheckConstraint(
            "frequency IN ('daily', 'weekdays', 'weekends', 'weekly', 'custom') "
            "OR frequency IS NULL",
            name="ck_habits_frequency",
        ),
        sa.CheckConstraint(
            "notification_frequency IN ("
            "'daily', 'every_other_day', 'twice_week', 'weekly', 'graduated', 'none')",
            name="ck_habits_notification_frequency",
        ),
        sa.CheckConstraint(
            "scaffolding_status IN ('tracking', 'accountable', 'graduated')",
            name="ck_habits_scaffolding_status",
        ),
    )
    op.create_index("ix_habits_status", "habits", ["status"])
    op.create_index("ix_habits_routine_id", "habits", ["routine_id"])


def downgrade() -> None:
    op.drop_index("ix_habits_routine_id", table_name="habits")
    op.drop_index("ix_habits_status", table_name="habits")
    op.drop_table("habits")
