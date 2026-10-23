"""
سجل حركة مبالغ الأهداف (goal_movements) — الدفعة 0.C.

كل تغيير بـ goals.current_amount لازم يمر من هنا كسطر إضافة فقط (append-only، ما بنعدّله ولا بنحذفه إلا مع الهدف نفسه):
  مبلغ موقّع: موجب = إضافة، سالب = عكس/تصفير.
  current_amount يبقى مخزّنًا للسرعة، ولازم يساوي مجموع حركات الهدف (يفحصه verify_money_integrity والاختبارات).
  cycle: دورة الهدف المتكرر وقت الحركة ("YYYY-MM")، و NULL للهدف غير المتكرر — بيستخدمه عكس التوزيع (0.D).
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class GoalMovement(Base):
    __tablename__ = "goal_movements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    cycle: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
