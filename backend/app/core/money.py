"""
أدوات المبالغ المالية — الدفعة 0.B.

القرار المعتمد: الدينار الأردني = 3 خانات عشرية (فلس) → الأعمدة NUMERIC(14,3)،
وكل حسابات الأرصدة بـ Decimal (مش float). هالملف المصدر الوحيد للتقريب والتحقق.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Annotated, Any

from pydantic import BeforeValidator

MONEY_DECIMALS = 3
MONEY_QUANT = Decimal("0.001")

# فرق أصغر من هيك بين الرقم ومقرّبه لـ 3 خانات = "ضجيج" أرقام عشرية ثنائية (مثل 0.1 + 0.2
# بالموبايل = 0.30000000000000004)، مش مبلغ حقيقي بأقل من فلس. بنتسامح معه ونقرّبه.
_FLOAT_NOISE = Decimal("1e-9")


def to_money(value: Any) -> Decimal:
    """يحوّل أي قيمة (Decimal/int/float/str) لـ Decimal مقرّب لـ 3 خانات.
    الـ float بيتحوّل عبر repr (مش Decimal(float) المباشر) عشان ما نورّث أخطاء التمثيل الثنائي."""
    if value is None:
        raise TypeError("to_money: القيمة None")
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, float):
        number = Decimal(repr(value))
    else:
        number = Decimal(str(value))
    return number.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def normalize_money_input(value: Any) -> Any:
    """
    يشتغل قبل تحقق Pydantic على مبالغ المدخلات:
    - float بضجيج ثنائي (≤ 1e-9 عن أقرب فلس) → يتقرّب بصمت لـ 3 خانات.
    - مبلغ بأكتر من 3 خانات فعليًا (مثل 10.0004) → بيترك كما هو، فيرفضه تحقق decimal_places بـ 422.
    - int / str / Decimal → كما هي.
    """
    if isinstance(value, float):
        try:
            number = Decimal(repr(value))
            if not number.is_finite():
                return value  # NaN/inf: يرفضها تحقق Decimal نفسه
            rounded = number.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            return value
        return rounded if abs(number - rounded) <= _FLOAT_NOISE else number
    return value


# نوع مدخلات المبالغ بالـ schemas: Decimal + تسامح مع ضجيج الـ float. الحدود (gt / max_digits / decimal_places)
# بتنحط على الحقل نفسه بـ Field(...).
MoneyIn = Annotated[Decimal, BeforeValidator(normalize_money_input)]
