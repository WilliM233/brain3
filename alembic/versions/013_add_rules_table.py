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

"""Add rules table and FK on notification_queue.rule_id.

Revision ID: 13a1b2c3d4e5
Revises: 12a1b2c3d4e5
Create Date: 2026-04-15

"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "13a1b2c3d4e5"
down_revision: Union[str, None] = "12a1b2c3d4e5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

# Postgres enum types for the rules engine
rule_entity_type = sa.Enum(
    "habit", "task", "routine", "checkin",
    name="ruleentitytype",
    create_constraint=False,
)
rule_metric = sa.Enum(
    "consecutive_skips", "days_untouched", "non_responses", "streak_length",
    name="rulemetric",
    create_constraint=False,
)
rule_operator = sa.Enum(
    ">=", "<=", "==",
    name="ruleoperator",
    create_constraint=False,
)
rule_action = sa.Enum(
    "create_notification",
    name="ruleaction",
    create_constraint=False,
)


def upgrade() -> None:
    # Create the rules table (Postgres enum types are created automatically)
    op.create_table(
        "rules",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("entity_type", rule_entity_type, nullable=False),
        sa.Column("entity_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("metric", rule_metric, nullable=False),
        sa.Column("operator", rule_operator, nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column(
            "action", rule_action, nullable=False,
            server_default="create_notification",
        ),
        sa.Column("notification_type", sa.String(), nullable=False),
        sa.Column("message_template", sa.Text(), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "cooldown_hours", sa.Integer(), nullable=False,
            server_default=sa.text("24"),
        ),
        sa.Column(
            "last_triggered_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "notification_type IN ("
            "'habit_nudge', 'routine_checklist', 'checkin_prompt', "
            "'time_block_reminder', 'deadline_event_alert', "
            "'pattern_observation', 'stale_work_nudge')",
            name="ck_rules_notification_type",
        ),
    )

    op.create_index(
        "ix_rules_entity_lookup", "rules",
        ["entity_type", "enabled"],
    )
    op.create_index(
        "ix_rules_entity_scoped", "rules",
        ["entity_type", "entity_id"],
    )

    # 3. Add FK constraint on notification_queue.rule_id → rules.id
    op.create_foreign_key(
        "fk_nq_rule_id",
        "notification_queue", "rules",
        ["rule_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # 1. Drop the FK constraint
    op.drop_constraint("fk_nq_rule_id", "notification_queue", type_="foreignkey")

    # 2. Drop indexes and the rules table
    op.drop_index("ix_rules_entity_scoped", table_name="rules")
    op.drop_index("ix_rules_entity_lookup", table_name="rules")
    op.drop_table("rules")

    # 3. Drop the Postgres enum types
    rule_action.drop(op.get_bind(), checkfirst=True)
    rule_operator.drop(op.get_bind(), checkfirst=True)
    rule_metric.drop(op.get_bind(), checkfirst=True)
    rule_entity_type.drop(op.get_bind(), checkfirst=True)
