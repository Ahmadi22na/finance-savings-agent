import enum

from sqlalchemy import String, Boolean, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class CategoryType(str, enum.Enum):
    """
    نوع التصنيف: بيحدد وين يظهر بواجهة التسجيل السريع.
    EXPENSE تظهر لما المستخدم يسجّل مصروف، INCOME لما يسجّل دخل،
    BOTH تظهر بالحالتين (مثال: "تحويل بين حسابات").
    """
    EXPENSE = "expense"
    INCOME = "income"
    BOTH = "both"


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
    category_type: Mapped[CategoryType] = mapped_column(
        SAEnum(CategoryType, name="category_type_enum"), default=CategoryType.EXPENSE
    )

    # كلمات مفتاحية (عامية + فصحى) تُستخدم بمحرك التصنيف الذكي المبدئي (Rule-Based)
    # قبل ما يتفعّل Gemini لاحقًا. مثال لتصنيف "مطاعم": ["مطعم", "أكل", "برجر", "بيتزا"]
    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")
