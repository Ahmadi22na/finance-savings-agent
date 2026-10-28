"""internal transfers: transactions.is_transfer + transfer_group_id (+ DB-level consistency)

Revision ID: f9b6d2e4a8c3
Revises: e8a5c1d3f7b2
Create Date: 2026-10-24

المرحلة 1 / الدفعة 1.B. إضافة فقط وبدون backfill: كل المعاملات الحالية is_transfer = false (معاملات عادية).
- قيد CHECK: المعاملة العادية بدون transfer_group_id، وطرف التحويل لازم يكون له مجموعة وحساب.
- فهرس فريد جزئي (transfer_group_id, type) لأطراف التحويل فقط: خروج واحد ودخول واحد على الأكثر لكل مجموعة.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f9b6d2e4a8c3'
down_revision: Union[str, None] = 'e8a5c1d3f7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('transactions', sa.Column('is_transfer', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('transactions', sa.Column('transfer_group_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_transactions_transfer_group_id', 'transactions', ['transfer_group_id'])
    op.create_check_constraint(
        'ck_transactions_transfer_consistency', 'transactions',
        "(NOT is_transfer AND transfer_group_id IS NULL) OR "
        "(is_transfer AND transfer_group_id IS NOT NULL AND account_id IS NOT NULL)",
    )
    op.create_index(
        'uq_transactions_transfer_group_type', 'transactions', ['transfer_group_id', 'type'],
        unique=True, postgresql_where=sa.text('is_transfer'),
    )


def downgrade() -> None:
    op.drop_index('uq_transactions_transfer_group_type', table_name='transactions')
    op.drop_constraint('ck_transactions_transfer_consistency', 'transactions', type_='check')
    op.drop_index('ix_transactions_transfer_group_id', table_name='transactions')
    op.drop_column('transactions', 'transfer_group_id')
    op.drop_column('transactions', 'is_transfer')
