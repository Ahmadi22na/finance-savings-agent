"""add transaction category origin and confidence

يميّز بين تصنيف اختاره المستخدم (user) وتصنيف خمّنه التطبيق تلقائيًا (auto) مع درجة الثقة،
عشان الواجهة تعرض شارة واضحة وتسمح بالتصحيح. المعاملات القديمة بتضل NULL (غير معروف).

Revision ID: a3c9e5b7d1f4
Revises: f2a8b4c6d1e3
Create Date: 2026-10-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a3c9e5b7d1f4'
down_revision: Union[str, None] = 'f2a8b4c6d1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    origin_enum = postgresql.ENUM('USER', 'AUTO', name='category_origin_enum')
    origin_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('transactions', sa.Column(
        'category_origin',
        postgresql.ENUM('USER', 'AUTO', name='category_origin_enum', create_type=False),
        nullable=True,
    ))
    op.add_column('transactions', sa.Column('category_confidence', sa.Numeric(precision=3, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('transactions', 'category_confidence')
    op.drop_column('transactions', 'category_origin')
    postgresql.ENUM(name='category_origin_enum').drop(op.get_bind(), checkfirst=True)
