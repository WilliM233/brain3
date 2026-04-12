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

"""create routine_completions table

Revision ID: 09b2c3d4e5f6
Revises: 08a1b2c3d4e5
Create Date: 2026-04-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "09b2c3d4e5f6"
down_revision: Union[str, None] = "08a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "routine_completions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("routine_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("routines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_at", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("freeform_note", sa.Text(), nullable=True),
        sa.Column("reconciled", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('all_done', 'partial', 'skipped')",
            name="ck_routine_completions_status",
        ),
    )
    op.create_index(
        "ix_routine_completions_routine_completed",
        "routine_completions",
        ["routine_id", "completed_at"],
    )
    op.create_index(
        "ix_routine_completions_reconciled",
        "routine_completions",
        ["reconciled"],
    )


def downgrade() -> None:
    op.drop_index("ix_routine_completions_reconciled", table_name="routine_completions")
    op.drop_index("ix_routine_completions_routine_completed", table_name="routine_completions")
    op.drop_table("routine_completions")
