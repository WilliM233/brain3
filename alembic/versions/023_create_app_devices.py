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

"""Create app_devices table.

Revision ID: 23a1b2c3d4e5
Revises: 22a1b2c3d4e5
Create Date: 2026-04-27

Stores FCM device registrations for the companion app. Phase 2 is
single-user, so the table has no user_id — every registered device
receives every push. ``platform`` is constrained to ``android | ios``
to future-proof the schema for APNs even though v2.0.0 ships
Android-only.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "23a1b2c3d4e5"
down_revision: Union[str, None] = "22a1b2c3d4e5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "app_devices",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("fcm_token", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "platform IN ('android', 'ios')",
            name="ck_app_devices_platform",
        ),
        sa.UniqueConstraint("fcm_token", name="uq_app_devices_fcm_token"),
    )


def downgrade() -> None:
    op.drop_table("app_devices")
