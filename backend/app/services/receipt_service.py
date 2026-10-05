"""
Receipt Scanning Service — Sprint 8 (OCR).

نفس فلسفة _ask_ai_for_category() بالضبط (agent_action_service.py): برومبت
واضح، رد JSON صارم، تحقق من صحة أي id يرجعه الموديل قبل ما نثق فيه. الفرق
الوحيد هون إنه المدخل صورة مش نص.

قرار تصميم مهم: هاد الملف ما بينشئ Transaction أبدًا. بيرجع بس "مسودة"
(Draft) للموبايل يعرضها بنفس شاشة التسجيل السريع الموجودة أصلاً، معبّاة
مسبقًا، ويراجعها المستخدم ويعدّلها قبل ما يحفظ — بالضبط زي ما كان مخطط له
بالخطة الأصلية ("مراجعة المستخدم للنتيجة قبل الحفظ، مهم لبناء الثقة").
هيك ما في احتمال نحفظ مبلغ غلط قرأه الـ OCR غلط بدون ما المستخدم ينتبه.
"""
import json
import logging

from sqlalchemy.orm import Session

from app.agent.providers.base import BaseAIProvider
from app.models.category import Category
from app.models.user import User
from app.schemas.transaction import ReceiptScanResult

logger = logging.getLogger("rasheed.agent")

# صيغ الصور يلي منقبلها فعليًا — نفس يلي Gemini Vision بيدعمها رسميًا
SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def scan_receipt(
    db: Session, user: User, provider: BaseAIProvider, image_bytes: bytes, mime_type: str
) -> ReceiptScanResult:
    categories = (
        db.query(Category)
        .filter(
            (Category.is_default.is_(True)) | (Category.user_id == user.id),
            Category.category_type.in_(["expense", "both"]),
        )
        .all()
    )
    category_lookup = {str(c.id): c.name for c in categories}
    category_options = "\n".join(f"- {cid}: {name}" for cid, name in category_lookup.items())

    prompt = (
        "هاي صورة فاتورة أو إيصال شراء. اقرأها واستخرج منها:\n"
        "1. المبلغ الإجمالي المدفوع (رقم فقط، بدون عملة)\n"
        "2. أنسب تصنيف من هالقائمة (id: اسم):\n"
        f"{category_options}\n"
        "3. اسم المحل أو وصف قصير مبني على محتوى الفاتورة\n\n"
        "لو الصورة مش واضحة أو مش فاتورة أصلًا، رجّع null للحقول يلي ما قدرت تقرأها.\n"
        "رد فقط بصيغة JSON صحيحة على هذا الشكل بالضبط، بدون أي نص إضافي قبله أو بعده:\n"
        '{"amount": <رقم أو null>, "category_id": "<id أو null>", "note": "<نص قصير أو null>"}'
    )

    reply = provider.analyze_image(
        system_prompt="أنت مساعد قراءة فواتير دقيق. رد بصيغة JSON فقط، بدون أي نص إضافي.",
        user_message=prompt,
        image_bytes=image_bytes,
        mime_type=mime_type,
    )

    if reply.raw_error:
        logger.error("Receipt scan AI call failed: %s", reply.raw_error)
        return ReceiptScanResult(amount=None, category_id=None, category_name=None, note=None, readable=False)

    # نتحمّل إنه بعض النماذج بترجع الـ JSON ملفوف بـ ```json ... ``` رغم التعليمات الصريحة
    cleaned = reply.text.strip().strip("`").removeprefix("json").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Could not parse receipt scan JSON: %r", reply.text)
        return ReceiptScanResult(amount=None, category_id=None, category_name=None, note=None, readable=False)

    amount = parsed.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        amount = None

    category_id = parsed.get("category_id")
    category_name = None
    if category_id not in category_lookup:
        # رشيد اقترح id مش موجود فعليًا بقائمتنا — نتجاهله بدل ما نرجّع بيانات فاسدة
        category_id = None
    else:
        category_name = category_lookup[category_id]

    note = parsed.get("note")
    if not isinstance(note, str) or not note.strip():
        note = None

    # "قابلة للقراءة" لو طلع منها رقم على الأقل — حتى لو التصنيف ما انعرف
    readable = amount is not None

    return ReceiptScanResult(
        amount=float(amount) if amount is not None else None,
        category_id=category_id,
        category_name=category_name,
        note=note,
        readable=readable,
    )
