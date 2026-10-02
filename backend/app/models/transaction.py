import enum
from datetime import datetime

from sqlalchemy import Numeric, Enum as SAEnum, ForeignKey, DateTime, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionSource(str, enum.Enum):
    """Transactionsource documentation."""
    MANUAL = "manual"
    OCR = "ocr"
    SMS = "sms"
    OPEN_BANKING = "open_banking"


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"




    __table_args__ = (
        UniqueConstraint("user_id", "external_ref", name="uq_transactions_user_external_ref"),
    )

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType, name="transaction_type_enum"))
    source: Mapped[TransactionSource] = mapped_column(SAEnum(TransactionSource, name="transaction_source_enum"))

    note: Mapped[str | None] = mapped_column(nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)



    raw_source_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    external_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped["User"] = relationship(back_populates="transactions")
    category: Mapped["Category | None"] = relationship(back_populates="transactions")
