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

"""migrate existing routines to container model

Revision ID: 10c3d4e5f6a7
Revises: 09b2c3d4e5f6
Create Date: 2026-04-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "10c3d4e5f6a7"
down_revision: Union[str, None] = "09b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO habits (
            id, routine_id, title, status, frequency,
            notification_frequency, scaffolding_status,
            introduced_at, graduation_window, graduation_target,
            graduation_threshold, current_streak, best_streak,
            last_completed, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), id, title, 'active', NULL,
            'none', 'tracking',
            CURRENT_DATE, 30, 0.85,
            30, current_streak, best_streak,
            last_completed, now(), now()
        FROM routines;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE routines r SET
            current_streak = COALESCE(
                (SELECT MAX(current_streak) FROM habits WHERE routine_id = r.id),
                r.current_streak),
            best_streak = COALESCE(
                (SELECT MAX(best_streak) FROM habits WHERE routine_id = r.id),
                r.best_streak),
            last_completed = COALESCE(
                (SELECT MAX(last_completed) FROM habits WHERE routine_id = r.id),
                r.last_completed);
        """
    )
    op.execute("DELETE FROM habits;")
