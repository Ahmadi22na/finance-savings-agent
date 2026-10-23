"""
SMS Import Service — Sprint 9، المرحلة 1 (استيراد يدوي من صندوق الوارد).

المبادئ (نفس فلسفة OCR والـ SMS الملصوق):
1. الموبايل يقرأ الرسائل ويفلتر محليًا (ما بيطلع من الجهاز إلا رسائل شكلها
   مالي)، وهون بنحلل ونقترح — المستخدم يختار شو يستورد. Preview ما بيحفظ شي.
2. الـ Confirm بيعيد التحليل من نص الرسالة نفسه على السيرفر: ما بنثق بأي
   مبلغ/نوع جاي من الموبايل أصلًا (الـ schema حتى ما فيه حقول لهالقيم).
3. منع التكرار بالبصمة (external_ref): hash من وقت استلام الرسالة ونصها.
   نفس النص بوقتين مختلفين = معاملتين مختلفتين (تحويلين متطابقين فعليًا)،
   ونفس الرسالة بنفس الوقت = معاملة وحدة مهما انستوردت مرات.
"""
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.money import to_money
from app.models.transaction import Transaction, TransactionSource, TransactionType
from app.models.user import User
from app.schemas.transaction import SmsImportCandidate, SmsMessageIn
from app.services import sms_parser_service


def _as_utc(moment: datetime) -> datetime:
    # توقيت بدون منطقة زمنية نعتبره UTC — الموبايل المفروض يبعت ISO بـ Z
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def compute_external_ref(body: str, received_at: datetime) -> str:
    raw = f"sms|{int(_as_utc(received_at).timestamp())}|{body.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_unique_messages(messages: list[SmsMessageIn]):
    """يحلل كل الرسائل، يتجاهل يلي ما انفهمت، وبيشيل التكرار داخل نفس الطلب."""
    seen: set[str] = set()
    items = []
    for message in messages:
        parsed = sms_parser_service.parse_sms(message.body)
        if parsed is None:
            continue
        ref = compute_external_ref(message.body, message.received_at)
        if ref in seen:
            continue
        seen.add(ref)
        items.append((message, parsed, ref))
    return items


def _existing_refs(db: Session, user: User, refs: list[str]) -> set[str]:
    if not refs:
        return set()
    rows = (
        db.query(Transaction.external_ref)
        .filter(Transaction.user_id == user.id, Transaction.external_ref.in_(refs))
        .all()
    )
    return {row[0] for row in rows}


# الدفعة 0.E: رسالة ملصوقة يدويًا (quick-log بمصدر sms) ما إلها بصمة، فاستيرادها لاحقًا بيعمل معاملة ثانية.
# بنعلّم المرشّح "ممكن مكرر" (تنبيه فقط، ما بنمنع شي) لو في معاملة ملصوقة بنفس المبلغ والنوع خلال هالنافذة.
POSSIBLE_DUPLICATE_WINDOW = timedelta(hours=24)


def _possible_duplicate_refs(db: Session, user: User, items, existing: set[str]) -> set[str]:
    """
    بصمات المرشّحين يلي غالبًا إلهم نظير ملصوق مسبقًا. المطابقة واحد-لواحد: المعاملة الملصوقة بتطابق أقرب رسالة بالوقت
    فقط، فتحويلين متطابقين فعليًا ولصقت واحد منهم = تنبيه على واحد بس.
    """
    pending = [(message, parsed, ref) for message, parsed, ref in items if ref not in existing]
    if not pending:
        return set()

    times = [_as_utc(message.received_at) for message, _, _ in pending]
    rows = (
        db.query(Transaction.id, Transaction.amount, Transaction.type, Transaction.occurred_at)
        .filter(
            Transaction.user_id == user.id,
            Transaction.source == TransactionSource.SMS,
            Transaction.external_ref.is_(None),
            Transaction.occurred_at >= min(times) - POSSIBLE_DUPLICATE_WINDOW,
            Transaction.occurred_at <= max(times) + POSSIBLE_DUPLICATE_WINDOW,
        )
        .all()
    )
    pasted = [(row.id, to_money(row.amount), row.type, _as_utc(row.occurred_at)) for row in rows]

    used: set = set()
    flagged: set[str] = set()
    for message, parsed, ref in sorted(pending, key=lambda item: _as_utc(item[0].received_at)):
        received_at = _as_utc(message.received_at)
        amount, kind = to_money(parsed.amount), TransactionType(parsed.type)
        best = None
        for tx_id, tx_amount, tx_type, tx_time in pasted:
            if tx_id in used or tx_amount != amount or tx_type != kind:
                continue
            gap = abs(tx_time - received_at)
            if gap <= POSSIBLE_DUPLICATE_WINDOW and (best is None or gap < best[1]):
                best = (tx_id, gap)
        if best is not None:
            used.add(best[0])
            flagged.add(ref)
    return flagged


def preview_import(db: Session, user: User, messages: list[SmsMessageIn]) -> list[SmsImportCandidate]:
    items = _parse_unique_messages(messages)
    existing = _existing_refs(db, user, [ref for _, _, ref in items])
    possible_duplicates = _possible_duplicate_refs(db, user, items, existing)

    candidates = [
        SmsImportCandidate(
            body=message.body.strip(),
            received_at=_as_utc(message.received_at),
            amount=float(parsed.amount),
            type=TransactionType(parsed.type),
            note=parsed.note,
            already_imported=ref in existing,
            possible_duplicate=ref in possible_duplicates,
        )
        for message, parsed, ref in items
    ]
    candidates.sort(key=lambda c: c.received_at, reverse=True)
    return candidates


def confirm_import(db: Session, user: User, messages: list[SmsMessageIn]) -> list[Transaction]:
    items = _parse_unique_messages(messages)
    existing = _existing_refs(db, user, [ref for _, _, ref in items])

    created: list[Transaction] = []
    for message, parsed, ref in items:
        if ref in existing:
            continue  # انستوردت قبل — تجاهل بصمت، مش خطأ
        transaction = Transaction(
            user_id=user.id,
            category_id=None,  # وصف تحويل مالي مجرد، ما بنخمّن له تصنيف — المستخدم يصنفها لاحقًا
            amount=parsed.amount,
            type=TransactionType(parsed.type),
            source=TransactionSource.SMS,
            note=parsed.note,
            occurred_at=_as_utc(message.received_at),
            external_ref=ref,
            # بدون نص الرسالة: فيه الرصيد ورقم الهاتف وما في داعي نخزّنه. البصمة (external_ref) كافية لمنع التكرار.
            raw_source_data=None,
        )
        db.add(transaction)
        created.append(transaction)

    try:
        db.commit()
    except IntegrityError:
        # طلبين استيراد متزامنين لنفس الرسائل — قيد UNIQUE بقاعدة البيانات أوقف الثاني
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="بعض هالرسائل انستوردت للتو بطلب ثاني — حدّث القائمة وجرب من جديد",
        )

    for transaction in created:
        db.refresh(transaction)
    return created
