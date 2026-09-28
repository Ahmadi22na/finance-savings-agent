import uuid

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class IncomeAllocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    سجل توزيع جزء من معاملة دخل واحدة على خطة معيّنة (خطة عادية أو "مصروف
    ثابت شهري" — نفس الجدول). بيسمح نقسّم دخل واحد (راتب 300 دينار مثلاً)
    على أكتر من خطة بمبالغ مختلفة، مع سجل واضح مين أخذ كم من أي دخل —
    مهم للتدقيق ومستقبلاً لعرض "من وين جاء تقدم هالخطة" للمستخدم.
    """
    __tablename__ = "income_allocations"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE")
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE")
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
