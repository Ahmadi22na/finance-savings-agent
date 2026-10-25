"""
الحسابات المالية (كاش/بنك/محفظة) ولقطات الرصيد اليدوية — المرحلة 1 (الدفعة 1.A).

مبادئ ثابتة:
- الاسم `FinancialAccount` (مش `Account`) لأن `account_service` عندنا = حذف حساب المستخدم.
- الرصيد ما بينخزّن بالحساب: = آخر لقطة (account_balance_snapshots) + حركة المعاملات المرتبطة بعدها (محسوب).
- اللقطات إضافة فقط (append-only)؛ حساب عليه معاملات أو لقطات ما بينحذف، بينؤرشف (is_active=false).
- اسم الحساب فريد لكل مستخدم بدون حساسية لحالة الأحرف، على مستوى القاعدة (فهرس فريد على lower(name)).
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.database.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

ACCOUNT_KINDS = ("cash", "bank", "wallet")


class FinancialAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (CheckConstraint("kind IN ('cash', 'bank', 'wallet')", name="ck_financial_accounts_kind"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="JOD", server_default="JOD")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=expression.true())


Index("uq_financial_accounts_user_lower_name", FinancialAccount.user_id, func.lower(FinancialAccount.name), unique=True)


class AccountBalanceSnapshot(UUIDPrimaryKeyMixin, Base):
    """لقطة رصيد مرجعية: "رصيد هذا الحساب كان كذا بوقت as_of". المبلغ موقّع (السالب مسموح: سحب على المكشوف)."""

    __tablename__ = "account_balance_snapshots"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual", server_default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
