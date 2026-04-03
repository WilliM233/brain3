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

"""add activity_tags association table

Revision ID: a1b2c3d4e5f6
Revises: 5ccf2b58d02a
Create Date: 2026-04-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "5ccf2b58d02a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activity_tags",
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["activity_id"], ["activity_log.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("activity_id", "tag_id"),
    )


def downgrade() -> None:
    op.drop_table("activity_tags")
