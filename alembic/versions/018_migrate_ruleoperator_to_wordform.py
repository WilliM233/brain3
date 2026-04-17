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

"""Migrate ruleoperator Postgres enum from symbols to word-form labels.

Revision ID: 18a1b2c3d4e5
Revises: 17a1b2c3d4e5
Create Date: 2026-04-17

Migration 013 created the ``ruleoperator`` Postgres enum with labels
``('>=', '<=', '==')`` (the Python enum values). The SQLAlchemy model
binding uses ``native_enum=False``, which serializes enum names on write
(``'gte'``, ``'lte'``, ``'eq'``). The two disagree on every insert, so
``create_rule`` 500s on Postgres. See BRAIN artifact 30ea0871 for the
full investigation.

This migration rotates the native enum labels to match what the ORM
already writes — the word-form names. Paired with a one-line model flip
to ``native_enum=True`` on the ``operator`` column, it unifies the
declaration with the schema. Rows are re-coerced via an explicit
``CASE`` mapping.
"""

from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "18a1b2c3d4e5"
down_revision: Union[str, None] = "17a1b2c3d4e5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE ruleoperator_new AS ENUM ('gte', 'lte', 'eq')")
    op.execute(
        """
        ALTER TABLE rules
        ALTER COLUMN operator TYPE ruleoperator_new
        USING CASE operator::text
            WHEN '>=' THEN 'gte'
            WHEN '<=' THEN 'lte'
            WHEN '==' THEN 'eq'
        END::ruleoperator_new
        """,
    )
    op.execute("DROP TYPE ruleoperator")
    op.execute("ALTER TYPE ruleoperator_new RENAME TO ruleoperator")


def downgrade() -> None:
    op.execute("CREATE TYPE ruleoperator_old AS ENUM ('>=', '<=', '==')")
    op.execute(
        """
        ALTER TABLE rules
        ALTER COLUMN operator TYPE ruleoperator_old
        USING CASE operator::text
            WHEN 'gte' THEN '>='
            WHEN 'lte' THEN '<='
            WHEN 'eq'  THEN '=='
        END::ruleoperator_old
        """,
    )
    op.execute("DROP TYPE ruleoperator")
    op.execute("ALTER TYPE ruleoperator_old RENAME TO ruleoperator")
