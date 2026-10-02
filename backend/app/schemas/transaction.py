import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.transaction import TransactionType, TransactionSource
from app.schemas.category import CategoryOut
from app.schemas.goal import GoalOut


class TransactionQuickLogCreate(BaseModel):
    """Transactionquicklogcreate documentation."""
    amount: float = Field(gt=0, description="المبلغ لازم يكون أكبر من صفر")
    type: TransactionType
    category_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=200)
    occurred_at: datetime | None = None

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


    ai_suggested: bool = False
    suggestion_confidence: float | None = None




    unallocated_amount: float = 0

    model_config = {"from_attributes": True}


class IncomeAllocationItem(BaseModel):
    goal_id: uuid.UUID
    amount: float = Field(gt=0)


class IncomeAllocationRequest(BaseModel):
    """Incomeallocationrequest documentation."""
    allocations: list[IncomeAllocationItem] = Field(min_length=1)


class IncomeAllocationResult(BaseModel):
    transaction: TransactionOut
    updated_goals: list[GoalOut]


class ReceiptScanResult(BaseModel):
    """Receiptscanresult documentation."""
    amount: float | None
    category_id: uuid.UUID | None
    category_name: str | None
    note: str | None


    readable: bool


class SmsParseRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000)


class SmsParseResult(BaseModel):
    """Smsparseresult documentation."""
    amount: float | None
    type: TransactionType | None
    note: str | None


    parsed: bool




class SmsMessageIn(BaseModel):
    body: str = Field(min_length=3, max_length=2000)
    received_at: datetime


class SmsImportPreviewRequest(BaseModel):


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
