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

"""Create notification_queue table.

Revision ID: 12a1b2c3d4e5
Revises: 11d4e5f6a7b8
Create Date: 2026-04-13

"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "12a1b2c3d4e5"
down_revision: Union[str, None] = "11d4e5f6a7b8"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "notification_queue",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("notification_type", sa.String(), nullable=False),
        sa.Column(
            "delivery_type",
            sa.String(),
            nullable=False,
            server_default="notification",
        ),
        sa.Column(
            "status", sa.String(), nullable=False, server_default="pending"
        ),
        sa.Column(
            "scheduled_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("target_entity_type", sa.String(), nullable=False),
        sa.Column("target_entity_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "canned_responses",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB, "postgresql"
            ),
            nullable=True,
        ),
        sa.Column("response", sa.String(), nullable=True),
        sa.Column("response_note", sa.Text(), nullable=True),
        sa.Column(
            "responded_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_by", sa.String(), nullable=False),
        sa.Column("rule_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "notification_type IN ("
            "'habit_nudge', 'routine_checklist', 'checkin_prompt', "
            "'time_block_reminder', 'deadline_event_alert', "
            "'pattern_observation', 'stale_work_nudge')",
            name="ck_notification_queue_notification_type",
        ),
        sa.CheckConstraint(
            "delivery_type IN ('notification')",
            name="ck_notification_queue_delivery_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'responded', 'expired')",
            name="ck_notification_queue_status",
        ),
        sa.CheckConstraint(
            "scheduled_by IN ('system', 'claude', 'rule')",
            name="ck_notification_queue_scheduled_by",
        ),
    )

    op.create_index(
        "ix_nq_scheduler_poll",
        "notification_queue",
        ["status", "scheduled_at"],
    )
    op.create_index(
        "ix_nq_expiry_check",
        "notification_queue",
        ["status", "expires_at"],
    )
    op.create_index(
        "ix_nq_target_lookup",
        "notification_queue",
        ["target_entity_type", "target_entity_id"],
    )
    op.create_index(
        "ix_nq_rule_traceability",
        "notification_queue",
        ["rule_id"],
    )
    op.create_index(
        "ix_nq_type_filter",
        "notification_queue",
        ["notification_type"],
    )
    op.create_index(
        "ix_nq_scheduled_by",
        "notification_queue",
        ["scheduled_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_nq_scheduled_by", table_name="notification_queue")
    op.drop_index("ix_nq_type_filter", table_name="notification_queue")
    op.drop_index("ix_nq_rule_traceability", table_name="notification_queue")
    op.drop_index("ix_nq_target_lookup", table_name="notification_queue")
    op.drop_index("ix_nq_expiry_check", table_name="notification_queue")
    op.drop_index("ix_nq_scheduler_poll", table_name="notification_queue")
    op.drop_table("notification_queue")
