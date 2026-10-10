"""
أدوات تمنع تسرب بيانات حساسة للسجلات (logs).

المشكلة: التطبيق بيتعامل مع رسائل بنكية وفواتير ومحادثات مالية، وأي سطر log فيه نص كامل أو مفتاح API
أو توكن ممكن يوصل لملفات السجلات أو لأدوات مراقبة خارجية. هون ثلاث طبقات حماية:

1. describe_text / safe_error: نسجّل "وصف" النص (طوله) بدل محتواه، ونقصّ رسائل الأخطاء.
2. SensitiveDataFilter: فلتر بيمسح المفاتيح والتوكنات وكلمات المرور من أي سطر log قبل ما ينكتب.
3. install_log_redaction(): بيركّب الفلتر على كل handlers (واحد مضمون للـ root عشان سجلات التطبيق).
"""
import logging
import re

_REDACTIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"AIza[0-9A-Za-z_\-]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bAQ\.[0-9A-Za-z_\-.]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"eyJ[0-9A-Za-z_\-]+\.[0-9A-Za-z_\-]+\.[0-9A-Za-z_\-]+"), "[REDACTED_JWT]"),
    (re.compile(r"(?i)\bBearer\s+[0-9A-Za-z_\-.=]+"), "Bearer [REDACTED]"),
    (
        re.compile(r"(?i)(password|passwd|secret|api[_-]?key|token)(['\"]?\s*[:=]\s*)(['\"]?)[^\s,'\"}&]+"),
        r"\1\2\3[REDACTED]",
    ),
]


def redact(text: str) -> str:
    """بيمسح المفاتيح والتوكنات وكلمات المرور من النص."""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def describe_text(text: object) -> str:
    """وصف آمن لنص حساس للـ logs: بنسجل طوله فقط، مش محتواه."""
    return f"<text len={len(str(text))}>"


def safe_error(error: object, limit: int = 300) -> str:
    """رسالة خطأ مقصوصة ومنقّاة من المفاتيح/التوكنات، مناسبة للـ logs."""
    return redact(str(error))[:limit]


class SensitiveDataFilter(logging.Filter):
    """فلتر بيمسح البيانات السرية من أي سطر log قبل كتابته."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 — ما بدنا الـ logging نفسه يكسر التطبيق
            return True
        redacted = redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


_FILTERED_LOGGERS = ("", "uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine")


def install_log_redaction() -> None:
    """
    بيركّب SensitiveDataFilter على كل handlers الموجودة (idempotent: ما بيتكرر لو انستدعى مرتين).
    ولو الـ root logger ما إله handler، بنضيف واحد بمستوى WARNING (نفس اللي كان يطلع تلقائيًا)
    عشان سجلات التطبيق (rasheed.*) تمر على الفلتر بدل ما تطلع مباشرة بدون حماية.
    """
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)

    for name in _FILTERED_LOGGERS:
        for handler in logging.getLogger(name).handlers:
            if not any(isinstance(f, SensitiveDataFilter) for f in handler.filters):
                handler.addFilter(SensitiveDataFilter())
