"""add user_active_days table

Revision ID: f2a8b4c6d1e3
Revises: e1f7a3b9c5d2
Create Date: 2026-10-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f2a8b4c6d1e3'
down_revision: Union[str, None] = 'e1f7a3b9c5d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_active_days',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'day', name='uq_user_active_days_user_day'),
    )
    op.create_index('ix_user_active_days_day', 'user_active_days', ['day'])


def downgrade() -> None:
    op.drop_index('ix_user_active_days_day', table_name='user_active_days')
    op.drop_table('user_active_days')
