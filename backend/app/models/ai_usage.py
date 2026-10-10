import enum
import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class AiUsageKind(str, enum.Enum):
    """أنواع استدعاءات الذكاء الاصطناعي الي بنحسبها ونحدّها (R11)."""
    CHAT = "chat"
    RECEIPT_SCAN = "receipt_scan"
    SUGGESTION = "suggestion"
    CATEGORIZE = "categorize"
    NUDGE = "nudge"


class AiUsageEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    سجل خفيف: مين (user_id) استدعى أي نوع (kind) ومتى (created_at). بدون أي محتوى للرسائل،
    فهو مناسب للخصوصية. بنعدّ الأحداث بآخر 24 ساعة (نافذة متحركة) لتطبيق الحدود اليومية،
    وبنحذف الأحداث الأقدم من 7 أيام تلقائيًا.
    kind مخزّن كنص عادي (مش DB enum) عشان إضافة نوع جديد ما تحتاج Migration.
    """
    __tablename__ = "ai_usage_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (
        Index("ix_ai_usage_events_user_kind_created", "user_id", "kind", "created_at"),
        Index("ix_ai_usage_events_created", "created_at"),
    )
