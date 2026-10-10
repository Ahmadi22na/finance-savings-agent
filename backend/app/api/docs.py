"""
توثيق OpenAPI المشترك: وصف التطبيق، شرح الـ Tags، وردود الأخطاء الشائعة.

الهدف إن صفحة Swagger (/docs) تكفي لأي مطوّر أو شريك تقني يقيّم المشروع بدون ما يقرأ الكود.
هالملف توثيق فقط — ما فيه أي منطق عمل.
"""
from pydantic import BaseModel, Field

APP_DESCRIPTION = """
**رشيد** تطبيق لإدارة المصاريف والتوفير، مبني حول وكيل ذكاء اصطناعي (رشيد) بثلاث شخصيات.
هذا الـ Backend بيخدّم تطبيق الموبايل (Flutter).

## البدء السريع (من هذه الصفحة)

1. نفّذ `POST /auth/register` (أو `POST /auth/login` إذا عندك حساب).
2. انسخ قيمة `access_token` من الرد.
3. اضغط زر **Authorize** أعلى الصفحة وألصق التوكن (بدون كلمة Bearer).
4. جرّب أي Endpoint محمي (القفل 🔒 بجانبه).

## مبادئ عامة

- **المصادقة:** JWT من نوع Bearer عبر الهيدر `Authorization: Bearer <access_token>`.
  كل الـ Endpoints محمية ما عدا `/auth/*` و`/personas` و`/health`.
- **العملة:** كل المبالغ بالدينار الأردني (JOD).
- **المسودات لا تحفظ شيئًا:** `/transactions/scan-receipt` و`/transactions/parse-sms`
  و`/transactions/sms-import/preview` تقرأ وتحلّل فقط. الحفظ الفعلي دايمًا بطلب منفصل
  يقرّره المستخدم بعد مراجعة المسودة.
- **رشيد لا يعدّل بياناتك بدون موافقة:** أي تغيير مالي يقترحه رشيد (تصحيح تصنيف، دفعة لهدف،
  هدف جديد، تسجيل دخل) يُنشأ كاقتراح بحالة `pending`، ولا يُنفَّذ إلا عند
  `POST /agent/actions/{id}/confirm` بطلب صريح من المستخدم.
- **ازدحام Gemini:** عند ازدحام خدمة الذكاء الاصطناعي، `/agent/chat` يرجّع `200` مع رسالة اعتذار
  داخل `reply` مع `ai_available=false` بدل خطأ HTTP (ولا تُحفظ الرسالة بسجل المحادثة، فإعادة الإرسال آمنة).

## صيغة الأخطاء

أخطاء المنطق ترجع بالشكل `{"detail": "رسالة بالعربي"}` مع كود HTTP مناسب
(400 طلب غير صالح، 401 غير مصادَق، 404 غير موجود، 409 تعارض).
أخطاء التحقق من المدخلات (Validation) ترجع `422` بالصيغة القياسية لـ FastAPI.
""".strip()

TAGS_METADATA = [
    {"name": "System", "description": "فحوصات حالة السيرفر."},
    {"name": "Auth", "description": "إنشاء الحساب وتسجيل الدخول (ترجع توكنات JWT)."},
    {"name": "Users", "description": "بيانات المستخدم الحالي."},
    {"name": "Onboarding", "description": "إعداد الحساب لأول مرة: نوع الدخل، شخصية رشيد، وأول هدف."},
    {"name": "Personas", "description": "شخصيات رشيد المتاحة للاختيار (عامة، بدون مصادقة)."},
    {"name": "Categories", "description": "تصنيفات المعاملات (الافتراضية + الخاصة بالمستخدم)."},
    {
        "name": "Goals",
        "description": (
            "الأهداف المالية (الخطط). تدعم الأولويات، والأهداف الشهرية المتكررة "
            "(مصاريف ثابتة تُصفَّر تلقائيًا كل شهر بعد اكتمالها)."
        ),
    },
    {
        "name": "Transactions",
        "description": (
            "تسجيل الدخل والمصروف: يدويًا (أيقونات أو نص ذكي)، من صورة فاتورة (OCR)، "
            "أو من الرسائل البنكية، مع توزيع الدخل على الأهداف."
        ),
    },
    {
        "name": "Agent",
        "description": "رشيد: المحادثة، الرسائل المبادِرة (Nudges)، والاقتراحات التي تحتاج موافقة المستخدم.",
    },
]


class ErrorResponse(BaseModel):
    """شكل الخطأ القياسي الراجع من كل الـ Endpoints."""

    detail: str = Field(description="رسالة الخطأ (بالعربي)")

    model_config = {"json_schema_extra": {"examples": [{"detail": "الهدف غير موجود"}]}}


def error_response(description: str) -> dict:
    return {"model": ErrorResponse, "description": description}


def responses(*parts: dict) -> dict:
    """دمج عدة قواميس ردود (لكل كود HTTP) بقاموس واحد."""
    merged: dict = {}
    for part in parts:
        merged.update(part)
    return merged


UNAUTHORIZED = {
    401: error_response("التوكن ناقص أو غير صالح أو منتهي الصلاحية، أو المستخدم غير موجود/غير مفعّل."),
}


def bad_request(description: str) -> dict:
    return {400: error_response(description)}


def not_found(description: str) -> dict:
    return {404: error_response(description)}


def conflict(description: str) -> dict:
    return {409: error_response(description)}
