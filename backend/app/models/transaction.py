import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Index, Numeric, Enum as SAEnum, ForeignKey, DateTime, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionSource(str, enum.Enum):
    """
    مصدر المعاملة — هذا الحقل هو قلب معمارية الـ Plugin.
    كل Plugin (Manual/OCR/SMS/لاحقًا OpenBanking) بيحدد قيمته هون،
    ورشيد والـ Analytics بيقدروا يميزوا مصدر كل بيانة بدون تعديل بالبنية.
    """
    MANUAL = "manual"
    OCR = "ocr"
    SMS = "sms"
    OPEN_BANKING = "open_banking"  # محجوز للمستقبل


class CategoryOrigin(str, enum.Enum):
    """
    مين حدّد تصنيف المعاملة:
    USER = المستخدم اختاره أو صحّحه (أو وافق على اقتراح رشيد)
    AUTO = التطبيق خمّنه تلقائيًا (قواعد/Gemini) ولسا المستخدم ما راجعه — بيظهر بشارة + درجة الثقة
    NULL = غير معروف (معاملة قديمة) أو بدون تصنيف
    """
    USER = "user"
    AUTO = "auto"


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"

    # بصمة المصدر الخارجي (مثلاً hash رسالة SMS) — تمنع استيراد نفس الرسالة مرتين.
    # القيد فريد لكل مستخدم على حدة، وقيم NULL (معاملات يدوية/OCR) مسموحة بلا حدود
    # لأن NULL ما بتتساوى مع بعضها بقيود UNIQUE بـ PostgreSQL وSQLite.
    __table_args__ = (
        UniqueConstraint("user_id", "external_ref", name="uq_transactions_user_external_ref"),
        # التحويل الداخلي (المرحلة 1/1.B): المعاملة العادية بدون مجموعة، وطرف التحويل لازم يكون له مجموعة وحساب
        CheckConstraint(
            "(NOT is_transfer AND transfer_group_id IS NULL) OR "
            "(is_transfer AND transfer_group_id IS NOT NULL AND account_id IS NOT NULL)",
            name="ck_transactions_transfer_consistency",
        ),
        # بكل مجموعة تحويل طرف خروج واحد وطرف دخول واحد على الأكثر (مفروضة بالقاعدة)
        Index(
            "uq_transactions_transfer_group_type", "transfer_group_id", "type", unique=True,
            postgresql_where=text("is_transfer"), sqlite_where=text("is_transfer"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    # الدينار الأردني = 3 خانات (فلس) → NUMERIC(14,3) (الدفعة 0.B)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType, name="transaction_type_enum"))
    source: Mapped[TransactionSource] = mapped_column(SAEnum(TransactionSource, name="transaction_source_enum"))

    category_origin: Mapped[CategoryOrigin | None] = mapped_column(
        SAEnum(CategoryOrigin, name="category_origin_enum"), nullable=True
    )
    category_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)

    note: Mapped[str | None] = mapped_column(nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # يخزن البيانات الخام الأصلية من المصدر (نص رسالة SMS، نتيجة OCR الكاملة...)
    # مفيد جدًا للتصحيح (debugging) ولتحسين دقة الـ Parsers لاحقًا دون فقدان المعلومة الأصلية
    raw_source_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    external_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # الحساب المالي (اختياري، المرحلة 1): المعاملات القديمة تبقى NULL ولا تدخل بأي رصيد محسوب. بدون ondelete:
    # ما بنسمح بحذف حساب مستخدَم (بيتأرشف). الفهرس لحساب الرصيد.
    account_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_accounts.id"), nullable=True, index=True
    )

    # التحويل الداخلي بين حسابين للمستخدم: معاملتان (خروج expense من حساب، ودخول income لحساب) بنفس transfer_group_id،
    # بتنشأ وبتتعدّل وبتنحذف سوا. مستثناة من الدخل/المصروف الحقيقي (مزاج رشيد، المصاريف الأساسية، التوزيع، المقاييس).
    is_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=expression.false())
    transfer_group_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    user: Mapped["User"] = relationship(back_populates="transactions")
    category: Mapped["Category | None"] = relationship(back_populates="transactions")
