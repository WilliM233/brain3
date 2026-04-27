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

"""Add unique constraint on routine_completions (routine_id, completed_at, status).

Revision ID: 21a1b2c3d4e5
Revises: 20a1b2c3d4e5
Create Date: 2026-04-27

Backstops the routine completion idempotency check added to
``complete_routine`` in app/routers/routines.py. Same-status retries on
the same date dedup to the existing row; mixed-status records on the
same date (e.g. an ``all_done`` in the morning + a ``partial``
reconciliation note in the evening) remain allowed by including
``status`` in the constraint tuple.

The upgrade dedups any pre-existing duplicate ``(routine_id,
completed_at, status)`` rows by keeping ``MIN(id)`` per group before
adding the constraint, otherwise the index build would fail on existing
data. RoutineCompletion has no ``created_at`` column, so MIN(id) is the
deterministic stand-in.
"""

from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "21a1b2c3d4e5"
down_revision: Union[str, None] = "20a1b2c3d4e5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Dedup: keep MIN(id) per (routine_id, completed_at, status), drop the rest.
    op.execute(
        """
        DELETE FROM routine_completions a
        USING routine_completions b
        WHERE a.routine_id = b.routine_id
          AND a.completed_at = b.completed_at
          AND a.status = b.status
          AND a.id > b.id
        """
    )

    op.create_unique_constraint(
        "uq_routine_completions_routine_date_status",
        "routine_completions",
        ["routine_id", "completed_at", "status"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_routine_completions_routine_date_status",
        "routine_completions",
        type_="unique",
    )
