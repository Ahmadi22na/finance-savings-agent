import uuid

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class IncomeAllocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Incomeallocation documentation."""
    __tablename__ = "income_allocations"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE")
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE")
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
