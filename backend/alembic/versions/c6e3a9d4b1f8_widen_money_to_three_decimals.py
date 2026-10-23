"""widen money columns to NUMERIC(14,3) (JOD has 3 decimals)

Revision ID: c6e3a9d4b1f8
Revises: b5d2f8a1c3e6
Create Date: 2026-10-22

الدفعة 0.B. توسيع فقط: كل القيم الحالية (خانتين) بتنحفظ بالضبط وبتصير بثلاث خانات (… .50 → .500).
الـ downgrade بيرجّع لخانتين — وهاد بيقرّب أي مبلغ فيه فلس (3 خانات) فعليًا، فاعتبره مسار طوارئ فقط.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c6e3a9d4b1f8'
down_revision: Union[str, None] = 'b5d2f8a1c3e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    ('transactions', 'amount'),
    ('goals', 'target_amount'),
    ('goals', 'current_amount'),
    ('income_allocations', 'amount'),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table, column,
            existing_type=sa.Numeric(precision=12, scale=2),
            type_=sa.Numeric(precision=14, scale=3),
            existing_nullable=False,
        )


def downgrade() -> None:
    for table, column in reversed(_COLUMNS):
        op.alter_column(
            table, column,
            existing_type=sa.Numeric(precision=14, scale=3),
            type_=sa.Numeric(precision=12, scale=2),
            existing_nullable=False,
        )
