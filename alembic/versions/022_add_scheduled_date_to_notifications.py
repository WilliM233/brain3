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

"""Add notification_queue.scheduled_date.

Revision ID: 22a1b2c3d4e5
Revises: 21a1b2c3d4e5
Create Date: 2026-04-27

Calendar-day anchor for each queued notification — denormalized from
``scheduled_at`` on purpose so the companion app can filter the recent
view by device-local date without the server needing to know client TZ
(per Stream C v0.9 Q8 / E5). ``scheduled_at`` (tz-aware DateTime)
remains the source of truth for *when* the notification fires;
``scheduled_date`` records the calendar day the notification is *for*.

Backfill derives ``scheduled_date`` from ``scheduled_at::date`` for
existing rows. PostgreSQL casts a ``timestamptz`` to ``date`` using the
session's ``TimeZone`` setting, which BRAIN runs in UTC — that matches
the documented "server TZ" derivation new code uses on insert. The
column is added nullable, backfilled, then altered to NOT NULL so the
build does not depend on whether the table is populated at upgrade
time.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "22a1b2c3d4e5"
down_revision: Union[str, None] = "21a1b2c3d4e5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "notification_queue",
        sa.Column("scheduled_date", sa.Date(), nullable=True),
    )
    op.execute(
        "UPDATE notification_queue "
        "SET scheduled_date = scheduled_at::date "
        "WHERE scheduled_date IS NULL"
    )
    op.alter_column("notification_queue", "scheduled_date", nullable=False)
    op.create_index(
        "ix_nq_scheduled_date",
        "notification_queue",
        ["scheduled_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_nq_scheduled_date", table_name="notification_queue")
    op.drop_column("notification_queue", "scheduled_date")
