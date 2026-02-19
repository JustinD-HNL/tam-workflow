"""Add linear_state_id and label_ids_json to action_items

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"


def upgrade() -> None:
    op.add_column("action_items", sa.Column("linear_state_id", sa.String(255), nullable=True))
    op.add_column("action_items", sa.Column("label_ids_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("action_items", "label_ids_json")
    op.drop_column("action_items", "linear_state_id")
