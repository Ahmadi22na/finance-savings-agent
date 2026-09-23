"""add suggest_income_log action type

Revision ID: 3f8b1c9a4d27
Revises: 0edda5e70f41
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op


revision: str = '3f8b1c9a4d27'
down_revision: Union[str, None] = '0edda5e70f41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE agent_action_type_enum ADD VALUE IF NOT EXISTS 'SUGGEST_INCOME_LOG'")


def downgrade() -> None:
    # نفس ملاحظة الـ Migration السابقة — PostgreSQL ما بيدعم حذف قيمة enum
    # مباشرة، فما في تراجع تلقائي هون.
    pass
