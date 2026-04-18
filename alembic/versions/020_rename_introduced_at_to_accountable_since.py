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

"""Rename habits.introduced_at to habits.accountable_since.

Revision ID: 20a1b2c3d4e5
Revises: 19a1b2c3d4e5
Create Date: 2026-04-18

Pure column rename per D2 / [A-1] v2 Amendment 02. The field stores the
date a habit entered the accountable phase of the graduated scaffolding
loop — auto-populated on tracking→accountable transition and never
thereafter. The pre-rename name ``introduced_at`` read as "first
practiced," which did not match the semantic and would confuse
AI-unmediated users in the long-term Companion App.

``ALTER TABLE ... RENAME COLUMN`` on PostgreSQL preserves row data and
any indexes bound to the column. No data migration, no constraint
rebuild.
"""

from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20a1b2c3d4e5"
down_revision: Union[str, None] = "19a1b2c3d4e5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.alter_column("habits", "introduced_at", new_column_name="accountable_since")


def downgrade() -> None:
    op.alter_column("habits", "accountable_since", new_column_name="introduced_at")
