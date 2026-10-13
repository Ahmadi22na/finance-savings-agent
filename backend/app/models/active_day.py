import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class UserActiveDay(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    يوم نشاط واحد للمستخدم (فتح التطبيق/تسجيل الدخول)، سطر واحد كحد أقصى باليوم.
    هاد الجدول هو الشي الوحيد الجديد لقياس "العودة للاستخدام" (retention)؛ باقي المقاييس بتنحسب من
    الجداول الموجودة أصلًا (المستخدمين، الأهداف، المعاملات...) بدون أي تسجيل إضافي.
    بدون أي محتوى: لا جهاز، لا IP، لا شاشات، لا مبالغ. بيتحذف مع الحساب.
    """
    __tablename__ = "user_active_days"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_user_active_days_user_day"),
        Index("ix_user_active_days_day", "day"),
    )
