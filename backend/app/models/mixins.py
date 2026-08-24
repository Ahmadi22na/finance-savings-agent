"""
Mixins مشتركة تُستخدم عبر كل الـ Models لتجنب تكرار الكود (DRY).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    """
    نستخدم UUID بدل Auto-Increment Integer كمفتاح أساسي لسببين:
    1. أمان: الـ ID مش قابل للتخمين (مهم لتطبيق مالي).
    2. عملي: لو لاحقًا صار عندك أكثر من سيرفر/قاعدة بيانات (مثلاً بعد الشراكة)،
       الـ UUID ما بيتصادم، عكس الـ Auto-Increment.
    """
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """يسجل تلقائيًا وقت الإنشاء والتعديل لكل سجل — أساسي لأي نظام مالي (Audit Trail)."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
