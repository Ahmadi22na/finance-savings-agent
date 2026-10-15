"""add persona_feedback table

Revision ID: b5d2f8a1c3e6
Revises: a3c9e5b7d1f4
Create Date: 2026-10-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b5d2f8a1c3e6'
down_revision: Union[str, None] = 'a3c9e5b7d1f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'persona_feedback',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('persona_id', sa.UUID(), nullable=False),
        sa.Column('rating', sa.SmallInteger(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('rating BETWEEN 1 AND 5', name='ck_persona_feedback_rating'),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'persona_id', name='uq_persona_feedback_user_persona'),
    )
    op.create_index('ix_persona_feedback_persona', 'persona_feedback', ['persona_id'])


def downgrade() -> None:
    op.drop_index('ix_persona_feedback_persona', table_name='persona_feedback')
    op.drop_table('persona_feedback')
