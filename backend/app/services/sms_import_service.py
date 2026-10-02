"""Module documentation."""
import hashlib
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionSource, TransactionType
from app.models.user import User
from app.schemas.transaction import SmsImportCandidate, SmsMessageIn
from app.services import sms_parser_service


def _as_utc(moment: datetime) -> datetime:

    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def compute_external_ref(body: str, received_at: datetime) -> str:
    raw = f"sms|{int(_as_utc(received_at).timestamp())}|{body.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_unique_messages(messages: list[SmsMessageIn]):
    """ parse unique messages documentation."""
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


def preview_import(db: Session, user: User, messages: list[SmsMessageIn]) -> list[SmsImportCandidate]:
    items = _parse_unique_messages(messages)
    existing = _existing_refs(db, user, [ref for _, _, ref in items])

    candidates = [
        SmsImportCandidate(
            body=message.body.strip(),
            received_at=_as_utc(message.received_at),
            amount=parsed.amount,
            type=TransactionType(parsed.type),
            note=parsed.note,
            already_imported=ref in existing,
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
            continue
        transaction = Transaction(
            user_id=user.id,
            category_id=None,
            amount=parsed.amount,
            type=TransactionType(parsed.type),
            source=TransactionSource.SMS,
            note=parsed.note,
            occurred_at=_as_utc(message.received_at),
            external_ref=ref,
            raw_source_data={"sms_body": message.body.strip()},
        )
        db.add(transaction)
        created.append(transaction)

    try:
        db.commit()
    except IntegrityError:

        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="بعض هالرسائل انستوردت للتو بطلب ثاني — حدّث القائمة وجرب من جديد",
        )

    for transaction in created:
        db.refresh(transaction)
    return created
