import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.transaction import TransactionType, TransactionSource
from app.schemas.category import CategoryOut


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

    model_config = {"from_attributes": True}
