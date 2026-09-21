"""add estimated_monthly_essentials and suggest_goal_creation action type

Revision ID: 0edda5e70f41
Revises: 91f46c7b9d8e
Create Date: 2026-09-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0edda5e70f41'
down_revision: Union[str, None] = '91f46c7b9d8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('estimated_monthly_essentials', sa.Numeric(12, 2), nullable=True))

    # إضافة قيمة جديدة لنوع الـ Enum الموجود بقاعدة البيانات — PostgreSQL
    # بيسمح هيك بدون ما نحذف/نعيد إنشاء النوع كامل (وبالتالي بدون ما نلمس
    # الصفوف الموجودة أصلاً). لازم يشتغل خارج معاملة صريحة على بعض إصدارات
    # قديمة من Postgres، بس PostgreSQL 12+ (المستخدم بالمشروع) بيسمح فيها
    # جوا Migration عادي طالما ما بنستخدم القيمة بنفس الـ Transaction.
    op.execute("ALTER TYPE agent_action_type_enum ADD VALUE IF NOT EXISTS 'SUGGEST_GOAL_CREATION'")


def downgrade() -> None:
    op.drop_column('users', 'estimated_monthly_essentials')
    # ملاحظة: PostgreSQL ما بيدعم حذف قيمة enum مباشرة (DROP VALUE مش موجودة) —
    # التراجع عن إضافة القيمة نفسها يحتاج إعادة بناء النوع كامل، وهذا خطر
    # على بيانات موجودة لو فيه صفوف تستخدمها فعليًا. تركناها عن قصد بدون
    # تراجع هون؛ لو احتجتها فعليًا لاحقًا راجع التعامل يدويًا.
