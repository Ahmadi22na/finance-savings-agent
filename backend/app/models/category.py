from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    نظام تصنيفات هجين: تصنيفات افتراضية (is_default=True, user_id=None) موجودة لكل المستخدمين،
    بالإضافة لتصنيفات خاصة يقدر المستخدم يضيفها. هيك رشيد يقدر يقترح تصنيف تلقائي
    من نفس القائمة يلي المستخدم شايفها، بدون ما يفرض عليه تصنيفات غريبة.
    """
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str] = mapped_column(String(50), default="tag")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")
