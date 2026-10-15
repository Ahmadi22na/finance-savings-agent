import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, JSON, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class PersonaFeedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    تقييم مختصر (1-5 نجوم + وسوم جاهزة بدون نص حر) من المستخدم لشخصية معينة من شخصيات رشيد (R13).
    تقييم واحد لكل (مستخدم، شخصية) وبيتحدّث لو أعاد التقييم. بدون أي نص حر لتجنب بيانات شخصية.
    بيتحذف مع حساب المستخدم.
    """
    __tablename__ = "persona_feedback"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    persona_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("personas.id"))
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "persona_id", name="uq_persona_feedback_user_persona"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_persona_feedback_rating"),
        Index("ix_persona_feedback_persona", "persona_id"),
    )
