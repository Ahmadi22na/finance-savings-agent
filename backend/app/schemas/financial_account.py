import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.money import MoneyIn

AccountKind = Literal["cash", "bank", "wallet"]
BalanceQuality = Literal["unknown", "manual_confirmed", "derived", "stale"]

# مبلغ موقّع (السالب مسموح: سحب على المكشوف)، حتى 3 خانات (فلس)
SignedMoney = Annotated[MoneyIn, Field(max_digits=14, decimal_places=3)]


def clean_account_name(value: str) -> str:
    """تنظيف الاسم: إزالة الفراغات الزايدة. (الفرادة بدون حساسية لحالة الأحرف بتتحقق بالقاعدة نفسها.)"""
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("اسم الحساب لا يمكن أن يكون فارغًا")
    return cleaned


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60, description="اسم الحساب (فريد لكل مستخدم بدون حساسية لحالة الأحرف)")
    kind: AccountKind = Field(description="نوع الحساب: cash أو bank أو wallet")
    opening_balance: SignedMoney | None = Field(
        default=None,
        description="رصيد حالي اختياري: يُسجَّل كلقطة مرجعية بوقت الإنشاء. بدونه يبقى رصيد الحساب غير معروف (unknown).",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "محفظة الجيب", "kind": "cash", "opening_balance": 35.5},
                {"name": "حساب الراتب", "kind": "bank"},
            ]
        }
    }

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        return clean_account_name(value)


class AccountUpdate(BaseModel):
    """تعديل جزئي: الحقل غير المُرسَل لا يتغيّر. لازم حقل واحد على الأقل، ولا يقبل null."""

    name: str | None = Field(default=None, min_length=1, max_length=60, description="الاسم الجديد")
    kind: AccountKind | None = Field(default=None, description="النوع الجديد")
    is_active: bool | None = Field(default=None, description="false = أرشفة الحساب، true = إعادة تفعيله")

    model_config = {"json_schema_extra": {"examples": [{"name": "حساب الراتب (القديم)", "is_active": False}]}}

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str | None) -> str | None:
        return None if value is None else clean_account_name(value)

    @model_validator(mode="after")
    def _at_least_one(self):
        if not self.model_fields_set:
            raise ValueError("لازم ترسل حقل واحد على الأقل للتعديل")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"الحقل {field} ما بيقبل null")
        return self


class BalanceSnapshotCreate(BaseModel):
    amount: SignedMoney = Field(description="رصيد الحساب الفعلي بوقت as_of (قد يكون سالبًا)")
    as_of: datetime | None = Field(
        default=None, description="وقت الرصيد. الافتراضي: الآن. لا يقبل وقتًا بالمستقبل."
    )

    model_config = {"json_schema_extra": {"examples": [{"amount": 120.75}, {"amount": -15, "as_of": "2026-10-20T09:00:00Z"}]}}


class AccountOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: AccountKind
    currency: str = Field(description="دايمًا JOD حاليًا")
    is_active: bool = Field(description="false = حساب مؤرشف (لا يستقبل معاملات ولا لقطات جديدة، ويبقى سجله للمراجعة)")
    created_at: datetime
    balance: float | None = Field(
        description="الرصيد التقديري = آخر لقطة + معاملات الحساب التي وقتها بعد وقت اللقطة تمامًا. null إذا ما في لقطة."
    )
    balance_quality: BalanceQuality = Field(
        description=(
            "unknown: ما في لقطة. manual_confirmed: لقطة حديثة وما في معاملات بعدها. "
            "derived: لقطة حديثة + معاملات بعدها (تقدير يفترض اكتمال التسجيل). stale: آخر لقطة أقدم من 30 يوم."
        )
    )
    balance_as_of: datetime | None = Field(description="وقت آخر لقطة رصيد (null إذا ما في)")
    last_snapshot_amount: float | None = Field(description="مبلغ آخر لقطة")
    transactions_since_snapshot: int = Field(description="عدد المعاملات المحسوبة بعد اللقطة")
    ignored_before_snapshot: int = Field(
        description=(
            "عدد معاملات الحساب التي سُجّلت بعد اللقطة لكن وقتها أقدم منها (أو يساويها): لا تُحسب بالرصيد "
            "لأن اللقطة تُعتبر شاملة لها. نبّه المستخدم لو > 0."
        )
    )


class BalanceSnapshotOut(BaseModel):
    id: uuid.UUID
    amount: float
    as_of: datetime
    source: str = Field(description="manual حاليًا")
    created_at: datetime


class AccountsSummaryOut(BaseModel):
    total: float | None = Field(description="مجموع أرصدة الحسابات النشطة ذات الرصيد المعروف. null إذا ولا حساب معروف.")
    accounts_total: int = Field(description="عدد الحسابات النشطة")
    accounts_counted: int = Field(description="عدد الحسابات المحسوبة بالمجموع (رصيدها معروف)")
    has_unknown: bool = Field(description="يوجد حساب نشط بدون لقطة رصيد (غير معروف)")
    has_stale: bool = Field(description="يوجد حساب رصيده قديم (stale)")
    incomplete: bool = Field(description="true = المجموع ناقص أو قديم؛ لا تعرضه كأنه مؤكد")
