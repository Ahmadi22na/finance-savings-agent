import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.transaction import TransactionType, TransactionSource
from app.schemas.category import CategoryOut
from app.schemas.goal import GoalOut


class TransactionQuickLogCreate(BaseModel):
    """
    يدعم المسارين سوا:
    - مسار الأيقونات: يوصل category_id مباشرة → حفظ فوري بدون أي معالجة ذكاء اصطناعي
    - مسار النص الذكي: يوصل note بدون category_id → محرك التصنيف (Rule-based اليوم، Gemini لاحقًا)
      بيحاول يخمّن التصنيف تلقائيًا
    """
    amount: float = Field(gt=0, description="المبلغ لازم يكون أكبر من صفر")
    type: TransactionType
    category_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=200)
    occurred_at: datetime | None = None  # لو ما تحدد، بنعتبره الآن

    @model_validator(mode="after")
    def category_or_note_required(self):
        if self.category_id is None and not (self.note and self.note.strip()):
            raise ValueError("لازم تحدد تصنيف (category_id) أو تكتب ملاحظة نصية (note) على الأقل")
        return self


class TransactionOut(BaseModel):
    id: uuid.UUID
    amount: float
    type: TransactionType
    source: TransactionSource
    note: str | None
    occurred_at: datetime
    category: CategoryOut | None

    # معلومات شفافية: هل رشيد هو يلي حزر التصنيف، وقديش كان واثق من حزره
    ai_suggested: bool = False
    suggestion_confidence: float | None = None

    # بس لمعاملات الدخل: قديش لسا باقي من هالمبلغ ما اتوزع على أي خطة.
    # الموبايل يستخدمها يقرر يعرض شاشة "وين بدك تحط هالدخل؟" أو لأ.
    # دايمًا 0 لمعاملات المصروف (مفهوم التوزيع أصلاً خاص بالدخل بس).
    unallocated_amount: float = 0

    model_config = {"from_attributes": True}


class IncomeAllocationItem(BaseModel):
    goal_id: uuid.UUID
    amount: float = Field(gt=0)


class IncomeAllocationRequest(BaseModel):
    """توزيع دخل واحد (معاملة وحدة) على خطة أو أكتر دفعة وحدة."""
    allocations: list[IncomeAllocationItem] = Field(min_length=1)


class IncomeAllocationResult(BaseModel):
    transaction: TransactionOut
    updated_goals: list[GoalOut]


class ReceiptScanResult(BaseModel):
    """
    نتيجة قراءة فاتورة — مسودة بس، ما بتنشئ Transaction. الموبايل يعبّي فيها
    شاشة التسجيل السريع مسبقًا، والمستخدم يراجعها/يعدّلها قبل ما يحفظ فعليًا.
    """
    amount: float | None
    category_id: uuid.UUID | None
    category_name: str | None
    note: str | None
    # False لو الصورة مش واضحة أو مش فاتورة أصلًا (ولا حتى قدر يقرأ مبلغ) —
    # الموبايل يعرض رسالة "ما قدرنا نقرأ الفاتورة، جرب صورة أوضح" بهالحالة
    readable: bool


class SmsParseRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000)


class SmsParseResult(BaseModel):
    """
    نتيجة تحليل رسالة بنكية — مسودة بس، نفس فلسفة ReceiptScanResult تمامًا:
    ما بتنشئ أي Transaction، الموبايل يعبّي فيها شاشة التسجيل السريع
    والمستخدم يراجعها ويحفظها بنفسه.
    """
    amount: float | None
    type: TransactionType | None
    note: str | None
    # False لو النص ما طابق أي نمط مدعوم أصلًا (رسالة بنك غير مدعوم، أو نص
    # عشوائي مش رسالة بنكية) — الموبايل يعرض "ما قدرنا نفهم هاي الرسالة"
    parsed: bool


# ---------- استيراد رسائل بنكية من صندوق الوارد (Sprint 9 — المرحلة 1) ----------

class SmsMessageIn(BaseModel):
    body: str = Field(min_length=3, max_length=2000)
    received_at: datetime


class SmsImportPreviewRequest(BaseModel):
    # الموبايل بيفلتر محليًا ويبعت بس الرسائل يلي شكلها مالي — 300 سقف
    # كافي جدًا، ويحمي السيرفر من طلب ضخم بالغلط
    messages: list[SmsMessageIn] = Field(min_length=1, max_length=300)


class SmsImportCandidate(BaseModel):
    body: str
    received_at: datetime
    amount: float
    type: TransactionType
    note: str
    already_imported: bool


class SmsImportPreviewResponse(BaseModel):
    candidates: list[SmsImportCandidate]


class SmsImportConfirmRequest(BaseModel):
    messages: list[SmsMessageIn] = Field(min_length=1, max_length=300)
