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
    amount: float = Field(gt=0, description="المبلغ بالدينار، لازم يكون أكبر من صفر")
    type: TransactionType = Field(description="`income` دخل أو `expense` مصروف")
    category_id: uuid.UUID | None = Field(default=None, description="معرّف تصنيف من `GET /categories` (مسار الأيقونات)")
    note: str | None = Field(
        default=None,
        max_length=200,
        description="ملاحظة نصية؛ بدون `category_id` تُستخدم لتخمين التصنيف تلقائيًا",
    )
    occurred_at: datetime | None = Field(default=None, description="وقت المعاملة؛ لو ما تحدد، بنعتبره الآن")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"amount": 4.5, "type": "expense", "category_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"},
                {"amount": 12, "type": "expense", "note": "غدا مع الشباب"},
            ]
        }
    }

    @model_validator(mode="after")
    def category_or_note_required(self):
        if self.category_id is None and not (self.note and self.note.strip()):
            raise ValueError("لازم تحدد تصنيف (category_id) أو تكتب ملاحظة نصية (note) على الأقل")
        return self


class TransactionOut(BaseModel):
    id: uuid.UUID
    amount: float
    type: TransactionType
    source: TransactionSource = Field(description="مصدر المعاملة: `manual` أو `ocr` أو `sms` (و`open_banking` محجوز للمستقبل)")
    note: str | None
    occurred_at: datetime
    category: CategoryOut | None = Field(description="التصنيف، أو null إذا المعاملة غير مصنّفة")

    # معلومات شفافية: هل رشيد هو يلي حزر التصنيف، وقديش كان واثق من حزره
    ai_suggested: bool = False
    suggestion_confidence: float | None = None

    # بس لمعاملات الدخل: قديش لسا باقي من هالمبلغ ما اتوزع على أي خطة.
    # الموبايل يستخدمها يقرر يعرض شاشة "وين بدك تحط هالدخل؟" أو لأ.
    # دايمًا 0 لمعاملات المصروف (مفهوم التوزيع أصلاً خاص بالدخل بس).
    unallocated_amount: float = 0

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "amount": 45,
                    "type": "income",
                    "source": "manual",
                    "note": "أجرة يوم",
                    "occurred_at": "2026-10-06T14:41:00Z",
                    "category": None,
                    "ai_suggested": False,
                    "suggestion_confidence": None,
                    "unallocated_amount": 45,
                }
            ]
        },
    }


class IncomeAllocationItem(BaseModel):
    goal_id: uuid.UUID = Field(description="معرّف الهدف (نشط وتابع للمستخدم)")
    amount: float = Field(gt=0, description="المبلغ الموزَّع على هذا الهدف بالدينار")


class IncomeAllocationRequest(BaseModel):
    """توزيع دخل واحد (معاملة وحدة) على خطة أو أكتر دفعة وحدة."""
    allocations: list[IncomeAllocationItem] = Field(
        min_length=1,
        description="هدف أو أكثر؛ مجموع المبالغ لا يتجاوز المتاح من هذا الدخل ولا يتكرر نفس الهدف",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "allocations": [
                        {"goal_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "amount": 30},
                        {"goal_id": "9c1d2e4a-7b3f-4d58-a1c6-0e5f8b2d7a91", "amount": 15},
                    ]
                }
            ]
        }
    }


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
    readable: bool = Field(description="false إذا الصورة غير واضحة أو ليست فاتورة")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "amount": 12.5,
                    "category_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "category_name": "بقالة وسوبرماركت",
                    "note": "سوبرماركت",
                    "readable": True,
                }
            ]
        }
    }


class SmsParseRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000, description="نص الرسالة البنكية كما وصلت (CliQ)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"text": "Successfully received 4.500 JOD from 0791234567 Current balance JOD5,000.000 JOD."}
            ]
        }
    }


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
    parsed: bool = Field(description="false إذا النص لا يطابق أي نمط رسالة بنكية مدعوم")

    model_config = {
        "json_schema_extra": {
            "examples": [{"amount": 4.5, "type": "income", "note": "تحويل CliQ من 0791234567", "parsed": True}]
        }
    }


# ---------- استيراد رسائل بنكية من صندوق الوارد (Sprint 9 — المرحلة 1) ----------

class SmsMessageIn(BaseModel):
    body: str = Field(min_length=3, max_length=2000, description="نص الرسالة")
    received_at: datetime = Field(description="وقت وصول الرسالة على الجهاز")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "body": "Successfully received 4.500 JOD from 0791234567 Current balance JOD5,000.000 JOD.",
                    "received_at": "2026-10-06T14:41:00Z",
                }
            ]
        }
    }


class SmsImportPreviewRequest(BaseModel):
    # الموبايل بيفلتر محليًا ويبعت بس الرسائل يلي شكلها مالي — 300 سقف
    # كافي جدًا، ويحمي السيرفر من طلب ضخم بالغلط
    messages: list[SmsMessageIn] = Field(min_length=1, max_length=300)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "messages": [
                        {
                            "body": "Successfully received 4.500 JOD from 0791234567 Current balance JOD5,000.000 JOD.",
                            "received_at": "2026-10-06T14:41:00Z",
                        }
                    ]
                }
            ]
        }
    }


class SmsImportCandidate(BaseModel):
    body: str
    received_at: datetime
    amount: float
    type: TransactionType
    note: str
    already_imported: bool = Field(description="true إذا هذه الرسالة استُوردت سابقًا (لن تُستورد مرة ثانية)")


class SmsImportPreviewResponse(BaseModel):
    candidates: list[SmsImportCandidate]


class SmsImportConfirmRequest(BaseModel):
    messages: list[SmsMessageIn] = Field(
        min_length=1,
        max_length=300,
        description="الرسائل التي اختارها المستخدم من نتيجة المعاينة",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "messages": [
                        {
                            "body": "Successfully received 4.500 JOD from 0791234567 Current balance JOD5,000.000 JOD.",
                            "received_at": "2026-10-06T14:41:00Z",
                        }
                    ]
                }
            ]
        }
    }
