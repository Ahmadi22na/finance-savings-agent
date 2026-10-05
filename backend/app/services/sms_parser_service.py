"""
SMS Parsing Service — Sprint 9.

قرار تصميم مهم اتفقنا عليه: المستخدم يلصق نص الرسالة يدويًا (Copy-Paste)،
مش قراءة تلقائية عبر صلاحية READ_SMS — هاي الصلاحية شديدة التقييد بسياسة
Play Store (عمليًا مخصصة بس لتطبيقات الرسائل الافتراضية)، فتجنبناها بالكامل
بمرحلة التجربة الحالية (APK مباشر). لو قررنا لاحقًا نضيف قراءة تلقائية،
هاد الملف ما بيتغيّر إطلاقًا — بس بيضيف مصدر جديد يستدعي parse_sms() لكل
رسالة توصل، فهو أصلًا مصمم Plugin-style زي باقي مصادر البيانات
(Manual, OCR, لاحقًا SMS التلقائي) — كلهم بيرجّعوا نفس الشكل الموحّد.

نمط CliQ (نظام الدفع الفوري الوطني الأردني) نمط واحد بيغطي عدة بنوك دفعة
وحدة (كل البنوك المشتركة بـ CliQ بترسل نفس صيغة الرسالة تقريبًا)، مش بنك
محدد بس — هيك أول نمط مدعوم بيغطي مساحة واسعة من المستخدمين مباشرة.

ما بننشئ Transaction هون أبدًا — نفس فلسفة receipt_service.py بالضبط:
مسودة بس، المستخدم يراجعها بشاشة التسجيل السريع العادية قبل ما يحفظ.
"""
import re
from dataclasses import dataclass


@dataclass
class ParsedSms:
    amount: float
    type: str  # "income" | "expense"
    note: str


# مبلغ CliQ ممكن يجي قبل أو بعد "JOD" (شفنا الحالتين بنفس الرسائل الحقيقية:
# "4.500 JOD" بالاستلام، "JOD6.000" بالتحويل) — الـ Regex بيتقبل الحالتين
_CLIQ_RECEIVED_PATTERN = re.compile(
    r"successfully\s+received\s+(?:jod\s*)?(?P<amount>[\d,]+\.?\d*)\s*(?:jod\s*)?from\s+(?P<sender>\S+)",
    re.IGNORECASE,
)
_CLIQ_TRANSFER_PATTERN = re.compile(
    r"successful\s+transfer\s+of\s+(?:jod\s*)?(?P<amount>[\d,]+\.?\d*)\s*(?:jod\s*)?to\s+(?P<recipient>\S+)",
    re.IGNORECASE,
)


def parse_sms(text: str) -> ParsedSms | None:
    """
    يرجّع None لو النص ما طابق أي نمط مدعوم — الـ Route بيترجم هاد لرسالة
    واضحة للمستخدم ("ما قدرنا نفهم هاي الرسالة") بدل ما يخترع بيانات.
    """
    cleaned = text.strip()
    if not cleaned:
        return None

    match = _CLIQ_RECEIVED_PATTERN.search(cleaned)
    if match:
        return ParsedSms(
            amount=_to_float(match.group("amount")),
            type="income",
            note=f"تحويل CliQ من {match.group('sender')}",
        )

    match = _CLIQ_TRANSFER_PATTERN.search(cleaned)
    if match:
        return ParsedSms(
            amount=_to_float(match.group("amount")),
            type="expense",
            note=f"تحويل CliQ إلى {match.group('recipient')}",
        )

    return None


def _to_float(raw_amount: str) -> float:
    return float(raw_amount.replace(",", ""))
