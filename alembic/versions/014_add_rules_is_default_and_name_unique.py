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

"""Add is_default column and unique constraint on name to rules table.

Revision ID: 14a1b2c3d4e5
Revises: 13a1b2c3d4e5
Create Date: 2026-04-15

"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "14a1b2c3d4e5"
down_revision: Union[str, None] = "13a1b2c3d4e5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Add is_default column — False for existing user-created rules
    op.add_column(
        "rules",
        sa.Column(
            "is_default", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Unique constraint on name — natural key for idempotent seed upsert
    op.create_unique_constraint("uq_rules_name", "rules", ["name"])


def downgrade() -> None:
    op.drop_constraint("uq_rules_name", "rules", type_="unique")
    op.drop_column("rules", "is_default")
