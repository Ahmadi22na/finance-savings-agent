"""add external_ref to transactions (dedup for imported SMS)

Revision ID: b7c41e9d2a05
Revises: 75f4003d708f
Create Date: 2026-09-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b7c41e9d2a05'
down_revision: Union[str, None] = '75f4003d708f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'transactions',
        sa.Column('external_ref', sa.String(length=64), nullable=True),
    )
    # فريد لكل مستخدم — نفس الرسالة (نفس البصمة) ما تنستورد مرتين لنفس الشخص،
    # بس مستخدم ثاني يقدر يستوردها عادي. قيم NULL (المعاملات اليدوية/OCR) مش
    # مقيّدة أبدًا لأن NULL ما بتتساوى مع NULL بقيود UNIQUE.
    op.create_unique_constraint(
        'uq_transactions_user_external_ref', 'transactions', ['user_id', 'external_ref']
    )


def downgrade() -> None:
    op.drop_constraint('uq_transactions_user_external_ref', 'transactions', type_='unique')
    op.drop_column('transactions', 'external_ref')
