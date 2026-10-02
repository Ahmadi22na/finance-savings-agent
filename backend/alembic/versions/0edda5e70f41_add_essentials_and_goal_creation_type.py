"""add estimated_monthly_essentials and suggest_goal_creation action type

Revision ID: 0edda5e70f41
Revises: 91f46c7b9d8e
Create Date: 2026-09-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0edda5e70f41'
down_revision: Union[str, None] = '91f46c7b9d8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('estimated_monthly_essentials', sa.Numeric(12, 2), nullable=True))

    # PostgreSQL allows adding enum values, but older versions require it outside a transaction.
    op.execute("ALTER TYPE agent_action_type_enum ADD VALUE IF NOT EXISTS 'SUGGEST_GOAL_CREATION'")


def downgrade() -> None:
    op.drop_column('users', 'estimated_monthly_essentials')
    # PostgreSQL cannot remove enum values directly, so the downgrade leaves this value in place.
