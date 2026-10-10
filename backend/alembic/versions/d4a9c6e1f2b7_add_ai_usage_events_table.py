"""add ai_usage_events table

Revision ID: d4a9c6e1f2b7
Revises: b7c41e9d2a05
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4a9c6e1f2b7'
down_revision: Union[str, None] = 'b7c41e9d2a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_usage_events',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_usage_events_user_kind_created', 'ai_usage_events', ['user_id', 'kind', 'created_at'])
    op.create_index('ix_ai_usage_events_created', 'ai_usage_events', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_ai_usage_events_created', table_name='ai_usage_events')
    op.drop_index('ix_ai_usage_events_user_kind_created', table_name='ai_usage_events')
    op.drop_table('ai_usage_events')
