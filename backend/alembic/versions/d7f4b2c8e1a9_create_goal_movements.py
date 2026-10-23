"""create goal_movements ledger + opening balances

Revision ID: d7f4b2c8e1a9
Revises: c6e3a9d4b1f8
Create Date: 2026-10-22

الدفعة 0.C. جدول جديد (إضافة فقط) + ترحيل مبدئي: لكل هدف current_amount ≠ 0 بنضيف حركة "opening" بنفس المبلغ بالضبط،
فيصير مجموع الحركات = current_amount من اللحظة الأولى. ما بنغيّر أي مبلغ بجدول goals.
(gen_random_uuid() مدمجة بـ PostgreSQL 13+.)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd7f4b2c8e1a9'
down_revision: Union[str, None] = 'c6e3a9d4b1f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'goal_movements',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('cycle', sa.String(length=7), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_goal_movements_goal_id', 'goal_movements', ['goal_id'])

    op.execute(
        """
        INSERT INTO goal_movements (id, goal_id, amount, kind, cycle, created_at)
        SELECT gen_random_uuid(), id, current_amount, 'opening',
               CASE WHEN is_recurring THEN last_reset_month END, now()
        FROM goals
        WHERE current_amount <> 0
        """
    )


def downgrade() -> None:
    op.drop_index('ix_goal_movements_goal_id', table_name='goal_movements')
    op.drop_table('goal_movements')
