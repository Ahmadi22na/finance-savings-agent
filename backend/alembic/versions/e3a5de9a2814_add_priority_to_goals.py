"""add priority column to goals

Revision ID: e3a5de9a2814
Revises: 3f8b1c9a4d27
Create Date: 2026-09-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e3a5de9a2814'
down_revision: Union[str, None] = '3f8b1c9a4d27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "goals",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
    )

    # الخطط الموجودة أصلاً كلها priority=0 هلأ (من الـ server_default) —
    # هيك بيصير ترتيبها كلها متعادلة. نرتبها هون مرة وحدة حسب created_at
    # (الأقدم = أولوية أعلى، رقم أصغر) لكل مستخدم على حدة، عشان أول ما
    # يفتح المستخدم شاشة الخطط يلاقي ترتيب منطقي جاهز، مش عشوائي.
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE goals
        SET priority = ranked.new_priority
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY user_id ORDER BY created_at ASC
            ) - 1 AS new_priority
            FROM goals
        ) AS ranked
        WHERE goals.id = ranked.id
    """))


def downgrade() -> None:
    op.drop_column("goals", "priority")
