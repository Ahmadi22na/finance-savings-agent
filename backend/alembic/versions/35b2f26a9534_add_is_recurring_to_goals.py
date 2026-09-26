"""add is_recurring and last_reset_month to goals

Revision ID: 35b2f26a9534
Revises: e3a5de9a2814
Create Date: 2026-09-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '35b2f26a9534'
down_revision: Union[str, None] = 'e3a5de9a2814'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "goals",
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "goals",
        sa.Column("last_reset_month", sa.String(length=7), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("goals", "last_reset_month")
    op.drop_column("goals", "is_recurring")
