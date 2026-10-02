import enum

from sqlalchemy import String, Boolean, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class CategoryType(str, enum.Enum):
    """Categorytype documentation."""
    EXPENSE = "expense"
    INCOME = "income"
    BOTH = "both"


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Category documentation."""
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str] = mapped_column(String(50), default="tag")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    category_type: Mapped[CategoryType] = mapped_column(
        SAEnum(CategoryType, name="category_type_enum"), default=CategoryType.EXPENSE
    )



    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")
