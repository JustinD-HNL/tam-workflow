"""Add 'quarterly' to cadence_enum.

Revision ID: 006
Revises: 005
Create Date: 2026-04-21
"""

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE cadence_enum ADD VALUE IF NOT EXISTS 'quarterly'")


def downgrade() -> None:
    # PostgreSQL does not support removing a value from an enum type.
    # Rolling back would require recreating cadence_enum without 'quarterly'
    # and rewriting every column that references it — destructive and rarely wanted.
    pass
