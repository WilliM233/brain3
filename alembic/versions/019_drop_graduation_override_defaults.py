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

"""Drop scalar server_defaults on habit graduation override columns; backfill to NULL.

Revision ID: 19a1b2c3d4e5
Revises: 18a1b2c3d4e5
Create Date: 2026-04-18

The three override columns (``graduation_window``, ``graduation_target``,
``graduation_threshold``) were created by migration 007 with scalar
server_defaults (30 / 0.85 / 30). Those defaults made override detection
impossible: every habit shipped with the default value regardless of
intent, so the ``resolve_graduation_params`` resolver in ``[2G-01]``
could never distinguish "user override to 30" from "inherit 30 from
friction-tier default." The friction-aware path was unreachable.

Per D1 (BRAIN decision) and ``[A-1]`` v2 Amendment 01, this migration:
1. Backfills existing rows so all three columns are NULL.
2. Drops the server_default on each column.

NULL is now the only default. ``resolve_graduation_params`` fires its
friction-tier fallback for un-overridden habits.

The blanket backfill is safe per BRAIN + L confirmation: no legitimate
user overrides exist in prod — every row's values came from the scalar
defaults, so nulling them preserves no user intent.
"""

from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "19a1b2c3d4e5"
down_revision: Union[str, None] = "18a1b2c3d4e5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Backfill: every existing row gets NULL in all three override columns.
    # Safe per D1 blast-radius analysis (issue #182).
    op.execute(
        "UPDATE habits SET "
        "graduation_window = NULL, "
        "graduation_target = NULL, "
        "graduation_threshold = NULL"
    )

    # Drop the scalar server_defaults so future INSERTs leave columns NULL
    # unless the caller supplies an explicit override.
    op.alter_column("habits", "graduation_window", server_default=None)
    op.alter_column("habits", "graduation_target", server_default=None)
    op.alter_column("habits", "graduation_threshold", server_default=None)


def downgrade() -> None:
    # Restore the scalar server_defaults. Row values are not restored —
    # the pre-upgrade values were the same defaults, so the result is
    # equivalent for habits created before migration 019.
    op.alter_column("habits", "graduation_window", server_default="30")
    op.alter_column("habits", "graduation_target", server_default="0.85")
    op.alter_column("habits", "graduation_threshold", server_default="30")
