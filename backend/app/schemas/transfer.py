import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.core.money import MoneyIn

PositiveMoney = Annotated[MoneyIn, Field(gt=0, max_digits=14, decimal_places=3)]


class TransferCreate(BaseModel):
    from_account_id: uuid.UUID = Field(description="الحساب المحوَّل منه (نشط ويخص المستخدم)")
    to_account_id: uuid.UUID = Field(description="الحساب المحوَّل إليه (نشط ويخص المستخدم، ومختلف عن الأول)")
    amount: PositiveMoney = Field(description="المبلغ بالدينار (أكبر من صفر، حتى 3 خانات)")
    occurred_at: datetime | None = Field(default=None, description="وقت التحويل؛ الافتراضي الآن")
    note: str | None = Field(default=None, max_length=200, description="ملاحظة اختيارية تظهر على الطرفين")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "from_account_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "to_account_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                    "amount": 50,
                    "note": "تعبئة المحفظة",
                }
            ]
        }
    }


class TransferOut(BaseModel):
    transfer_group_id: uuid.UUID
    amount: float
    occurred_at: datetime
    note: str | None
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    out_transaction_id: uuid.UUID = Field(description="طرف الخروج (نوعه expense) من الحساب المحوَّل منه")
    in_transaction_id: uuid.UUID = Field(description="طرف الدخول (نوعه income) للحساب المحوَّل إليه")
