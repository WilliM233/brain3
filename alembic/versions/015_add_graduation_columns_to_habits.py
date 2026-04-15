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

"""Add friction_score, re_scaffold_count, last_frequency_changed_at to habits.

Revision ID: 15a1b2c3d4e5
Revises: 14a1b2c3d4e5
Create Date: 2026-04-15

"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15a1b2c3d4e5"
down_revision: Union[str, None] = "14a1b2c3d4e5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "habits",
        sa.Column("friction_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "habits",
        sa.Column(
            "re_scaffold_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "habits",
        sa.Column(
            "last_frequency_changed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_habits_friction_score",
        "habits",
        "friction_score IS NULL OR (friction_score >= 1 AND friction_score <= 5)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_habits_friction_score", "habits", type_="check")
    op.drop_column("habits", "last_frequency_changed_at")
    op.drop_column("habits", "re_scaffold_count")
    op.drop_column("habits", "friction_score")
