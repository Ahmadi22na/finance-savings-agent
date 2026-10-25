"""financial accounts + balance snapshots + transactions.account_id

Revision ID: e8a5c1d3f7b2
Revises: d7f4b2c8e1a9
Create Date: 2026-10-23

المرحلة 1 / الدفعة 1.A. إضافة فقط وبدون backfill: كل المعاملات الحالية تبقى account_id = NULL (بدون حساب).
- financial_accounts: اسم فريد لكل مستخدم بدون حساسية لحالة الأحرف (فهرس فريد على lower(name))، ونوع محصور بـ cash/bank/wallet.
- account_balance_snapshots: لقطات رصيد يدوية (إضافة فقط).
- transactions.account_id: اختياري. FK بدون حذف تتالي (NO ACTION): ما بينحذف حساب عليه معاملات حتى على مستوى القاعدة.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e8a5c1d3f7b2'
down_revision: Union[str, None] = 'd7f4b2c8e1a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'financial_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default='JOD', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("kind IN ('cash', 'bank', 'wallet')", name='ck_financial_accounts_kind'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_financial_accounts_user_id', 'financial_accounts', ['user_id'])
    op.create_index(
        'uq_financial_accounts_user_lower_name', 'financial_accounts', ['user_id', sa.text('lower(name)')], unique=True
    )

    op.create_table(
        'account_balance_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column('as_of', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(length=16), server_default='manual', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['financial_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_account_balance_snapshots_account_id', 'account_balance_snapshots', ['account_id'])

    op.add_column('transactions', sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_transactions_account_id', 'transactions', 'financial_accounts', ['account_id'], ['id'])
    op.create_index('ix_transactions_account_id', 'transactions', ['account_id'])


def downgrade() -> None:
    op.drop_index('ix_transactions_account_id', table_name='transactions')
    op.drop_constraint('fk_transactions_account_id', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'account_id')
    op.drop_index('ix_account_balance_snapshots_account_id', table_name='account_balance_snapshots')
    op.drop_table('account_balance_snapshots')
    op.drop_index('uq_financial_accounts_user_lower_name', table_name='financial_accounts')
    op.drop_index('ix_financial_accounts_user_id', table_name='financial_accounts')
    op.drop_table('financial_accounts')
