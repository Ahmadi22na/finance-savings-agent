"""add category_type and keywords to categories

Revision ID: fd931a6d75d4
Revises: 829d4055ba8b
Create Date: 2026-08-25 10:41:21.824785

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fd931a6d75d4'
down_revision: Union[str, None] = '829d4055ba8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


category_type_enum = sa.Enum('EXPENSE', 'INCOME', 'BOTH', name='category_type_enum')


def upgrade() -> None:
    # لازم ننشئ نوع الـ ENUM بشكل صريح أول — autogenerate ما بيضمن ترتيب إنشائه صح مع PostgreSQL
    category_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'categories',
        sa.Column('category_type', category_type_enum, nullable=False, server_default='EXPENSE'),
    )
    op.alter_column('categories', 'category_type', server_default=None)
    op.add_column('categories', sa.Column('keywords', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('categories', 'keywords')
    op.drop_column('categories', 'category_type')
    category_type_enum.drop(op.get_bind(), checkfirst=True)
