"""
الحسابات المالية اليدوية ولقطات الرصيد — المرحلة 1 / الدفعة 1.A.

قواعد الرصيد (مثبّتة بقرار المشروع، ومغطّاة باختبارات):
  الرصيد = مبلغ آخر لقطة + Σ(دخل − مصروف) لمعاملات الحساب التي  occurred_at  أكبر *تمامًا* من  as_of  اللقطة.
  1) آخر لقطة = الأحدث بـ as_of (والتعادل بـ created_at). اللقطات إضافة فقط، والقديمة تبقى للمراجعة.
  2) تساوي التوقيت: معاملة وقتها = as_of بالضبط *لا تُحسب* (نفترض اللقطة شاملة لها).
  3) معاملة بتاريخ أقدم من اللقطة (أو يساويها) *لا تُحسب* حتى لو سُجّلت بعد اللقطة بوقت طويل: اللقطة تعني "هذا رصيدي
     الفعلي بوقت كذا" فتشمل كل ما قبلها. هالحالة بنكشفها بعدّاد ignored_before_snapshot (معاملات سُجّلت بعد اللقطة
     ووقتها ≤ as_of) عشان الواجهة تنبّه المستخدم بدل ما نخفيها.
  4) معاملة بدون حساب (account_id NULL) أو بحساب ثاني: ما إلها أي أثر. ما في backfill لحساب افتراضي أبدًا.
  5) حساب بدون لقطة = رصيد غير معروف (null)، مش صفر.
الجودة (محسوبة، مش مخزّنة): unknown / stale (آخر لقطة أقدم من 30 يوم) / derived (+ معاملات بعدها) / manual_confirmed.
الحساب المؤرشف (is_active=false): ما بيستقبل لقطات جديدة (ولا معاملات بالدفعة 1.B)، ويبقى سجله ورصيده قابلين للمراجعة.
القفل: تعديل/حذف/لقطة بتقفل صف الحساب FOR UPDATE، فالحذف واللقطة المتزامنين بيتسلسلوا (إما يتحذف الحساب وما بينقبل
اللقطة، أو بتنقبل اللقطة والحذف بيرجع 409).
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.money import to_money
from app.models.financial_account import AccountBalanceSnapshot, FinancialAccount
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.financial_account import (
    AccountCreate,
    AccountOut,
    AccountsSummaryOut,
    AccountUpdate,
    BalanceSnapshotCreate,
    BalanceSnapshotOut,
)

STALE_AFTER = timedelta(days=30)
FUTURE_TOLERANCE = timedelta(minutes=5)  # فرق ساعات بين الجهاز والسيرفر
SNAPSHOT_HISTORY_LIMIT = 50


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get_or_404(db: Session, user: User, account_id: uuid.UUID, lock: bool = False) -> FinancialAccount:
    query = db.query(FinancialAccount).filter(FinancialAccount.id == account_id, FinancialAccount.user_id == user.id)
    if lock:
        query = query.populate_existing().with_for_update()
    account = query.first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الحساب غير موجود")
    return account


def lock_account_for_link(db: Session, user: User, account_id: uuid.UUID, lock: bool = True) -> FinancialAccount:
    """
    للمعاملات/التحويلات اللي بتنربط بحساب: الحساب لازم يخص المستخدم (غير هيك 404، بما فيها حقن account_id غريب)
    ولازم يكون نشط (المؤرشف 400). القفل مشترك (FOR SHARE): ربطات متزامنة ما بتعطّل بعضها، بس بتمنع حذف/أرشفة/لقطة
    على نفس الحساب (اللي بتاخد FOR UPDATE) تدخل بنص عملية الربط.
    lock=False: تحقق مبكر بدون قفل (قبل أي شغل غالي زي استدعاء الذكاء الاصطناعي).
    """
    query = db.query(FinancialAccount).filter(FinancialAccount.id == account_id, FinancialAccount.user_id == user.id)
    if lock:
        query = query.populate_existing().with_for_update(read=True)
    account = query.first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الحساب غير موجود")
    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="هذا الحساب مؤرشف ولا يستقبل حركات جديدة. أعد تفعيله أولاً.",
        )
    return account


def lock_accounts_for_link(db: Session, user: User, account_ids: list[uuid.UUID]) -> dict[uuid.UUID, FinancialAccount]:
    ids = list(dict.fromkeys(account_ids))
    accounts = (
        db.query(FinancialAccount)
        .filter(FinancialAccount.id.in_(ids), FinancialAccount.user_id == user.id)
        .order_by(FinancialAccount.id)
        .populate_existing()
        .with_for_update(read=True)
        .all()
    )
    found = {account.id: account for account in accounts}
    if set(found) != set(ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الحساب غير موجود")
    if any(not account.is_active for account in accounts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="هذا الحساب مؤرشف ولا يستقبل حركات جديدة. أعد تفعيله أولاً.",
        )
    return found


def _latest_snapshots(db: Session, account_ids: list[uuid.UUID]) -> dict[uuid.UUID, AccountBalanceSnapshot]:
    if not account_ids:
        return {}
    rows = (
        db.query(AccountBalanceSnapshot)
        .filter(AccountBalanceSnapshot.account_id.in_(account_ids))
        .order_by(
            AccountBalanceSnapshot.account_id,
            AccountBalanceSnapshot.as_of.desc(),
            AccountBalanceSnapshot.created_at.desc(),
        )
        .all()
    )
    latest: dict[uuid.UUID, AccountBalanceSnapshot] = {}
    for row in rows:
        latest.setdefault(row.account_id, row)  # أول سطر لكل حساب = الأحدث
    return latest


def _build_out(db: Session, account: FinancialAccount, snapshot: AccountBalanceSnapshot | None) -> AccountOut:
    balance = None
    quality = "unknown"
    as_of = None
    last_amount = None
    moved_count = 0
    ignored = 0

    if snapshot is not None:
        signed_amount = case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=-Transaction.amount)
        moved_total, moved_count = (
            db.query(func.coalesce(func.sum(signed_amount), 0), func.count(Transaction.id))
            .filter(Transaction.account_id == account.id, Transaction.occurred_at > snapshot.as_of)
            .one()
        )
        ignored = (
            db.query(func.count(Transaction.id))
            .filter(
                Transaction.account_id == account.id,
                Transaction.occurred_at <= snapshot.as_of,
                Transaction.created_at > snapshot.created_at,
            )
            .scalar()
        )
        last_amount = to_money(snapshot.amount)
        balance = last_amount + to_money(moved_total)
        as_of = _as_utc(snapshot.as_of)
        if datetime.now(timezone.utc) - as_of > STALE_AFTER:
            quality = "stale"
        elif moved_count:
            quality = "derived"
        else:
            quality = "manual_confirmed"

    return AccountOut(
        id=account.id,
        name=account.name,
        kind=account.kind,
        currency=account.currency,
        is_active=account.is_active,
        created_at=account.created_at,
        balance=None if balance is None else float(balance),
        balance_quality=quality,
        balance_as_of=as_of,
        last_snapshot_amount=None if last_amount is None else float(last_amount),
        transactions_since_snapshot=int(moved_count),
        ignored_before_snapshot=int(ignored or 0),
    )


def list_accounts(db: Session, user: User, include_archived: bool = False) -> list[AccountOut]:
    query = db.query(FinancialAccount).filter(FinancialAccount.user_id == user.id)
    if not include_archived:
        query = query.filter(FinancialAccount.is_active.is_(True))
    accounts = query.order_by(FinancialAccount.created_at, FinancialAccount.name).all()
    latest = _latest_snapshots(db, [a.id for a in accounts])
    return [_build_out(db, account, latest.get(account.id)) for account in accounts]


def get_account(db: Session, user: User, account_id: uuid.UUID) -> AccountOut:
    account = _get_or_404(db, user, account_id)
    return _build_out(db, account, _latest_snapshots(db, [account.id]).get(account.id))


def create_account(db: Session, user: User, data: AccountCreate) -> AccountOut:
    account = FinancialAccount(user_id=user.id, name=data.name, kind=data.kind)
    db.add(account)
    try:
        db.flush()  # هون بتنكشف مخالفة فرادة الاسم (حتى لو طلبين متزامنين)
        if data.opening_balance is not None:
            db.add(
                AccountBalanceSnapshot(
                    account_id=account.id,
                    amount=to_money(data.opening_balance),
                    as_of=datetime.now(timezone.utc),
                    source="manual",
                )
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="عندك حساب بنفس الاسم")
    except Exception:
        db.rollback()
        raise
    return get_account(db, user, account.id)


def update_account(db: Session, user: User, account_id: uuid.UUID, data: AccountUpdate) -> AccountOut:
    fields = data.model_fields_set
    try:
        account = _get_or_404(db, user, account_id, lock=True)
        if "name" in fields:
            account.name = data.name
        if "kind" in fields:
            account.kind = data.kind
        if "is_active" in fields:
            account.is_active = data.is_active
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="عندك حساب بنفس الاسم")
    except Exception:
        db.rollback()
        raise
    return get_account(db, user, account_id)


def delete_account(db: Session, user: User, account_id: uuid.UUID) -> None:
    """حذف فعلي فقط لحساب ما عليه أي معاملة ولا لقطة رصيد. غير هيك: 409 ويُؤرشف (is_active=false) مع حفظ السجل."""
    try:
        account = _get_or_404(db, user, account_id, lock=True)
        has_transactions = db.query(Transaction.id).filter(Transaction.account_id == account.id).first() is not None
        has_snapshots = (
            db.query(AccountBalanceSnapshot.id).filter(AccountBalanceSnapshot.account_id == account.id).first()
            is not None
        )
        if has_transactions or has_snapshots:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="هذا الحساب عليه معاملات أو لقطات رصيد، فما بينحذف حفاظًا على السجل. أرشفه بدل الحذف.",
            )
        db.delete(account)
        db.commit()
    except Exception:
        db.rollback()
        raise


def add_balance_snapshot(db: Session, user: User, account_id: uuid.UUID, data: BalanceSnapshotCreate) -> AccountOut:
    now = datetime.now(timezone.utc)
    try:
        account = _get_or_404(db, user, account_id, lock=True)
        if not account.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="الحساب مؤرشف: أعد تفعيله أولاً قبل تسجيل رصيد جديد",
            )
        as_of = _as_utc(data.as_of) if data.as_of is not None else now
        if as_of > now + FUTURE_TOLERANCE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="وقت الرصيد لا يمكن أن يكون بالمستقبل")
        db.add(AccountBalanceSnapshot(account_id=account.id, amount=to_money(data.amount), as_of=as_of, source="manual"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_account(db, user, account_id)


def list_snapshots(db: Session, user: User, account_id: uuid.UUID) -> list[BalanceSnapshotOut]:
    account = _get_or_404(db, user, account_id)
    rows = (
        db.query(AccountBalanceSnapshot)
        .filter(AccountBalanceSnapshot.account_id == account.id)
        .order_by(AccountBalanceSnapshot.as_of.desc(), AccountBalanceSnapshot.created_at.desc())
        .limit(SNAPSHOT_HISTORY_LIMIT)
        .all()
    )
    return [
        BalanceSnapshotOut(
            id=row.id, amount=float(to_money(row.amount)), as_of=_as_utc(row.as_of), source=row.source,
            created_at=_as_utc(row.created_at),
        )
        for row in rows
    ]


def summary(db: Session, user: User) -> AccountsSummaryOut:
    accounts = list_accounts(db, user, include_archived=False)
    counted = [a for a in accounts if a.balance is not None]
    total = None
    if counted:
        total = float(sum((to_money(a.balance) for a in counted), to_money(0)))
    has_unknown = any(a.balance_quality == "unknown" for a in accounts)
    has_stale = any(a.balance_quality == "stale" for a in accounts)
    return AccountsSummaryOut(
        total=total,
        accounts_total=len(accounts),
        accounts_counted=len(counted),
        has_unknown=has_unknown,
        has_stale=has_stale,
        incomplete=has_unknown or has_stale,
    )
