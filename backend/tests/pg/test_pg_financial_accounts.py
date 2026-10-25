"""
المرحلة 1 / الدفعة 1.A — التزامن الحقيقي على PostgreSQL. كل اختبار بيتحقق من الحالة النهائية بالقاعدة، مش من نجاح الطلبات فقط.
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException

from app.models.financial_account import AccountBalanceSnapshot, FinancialAccount
from app.models.user import User
from app.schemas.financial_account import AccountCreate, BalanceSnapshotCreate
from app.services import financial_account_service


def _make_user(db, phone="0790097101"):
    user = User(name="pg accounts", phone=phone, hashed_password="x")
    db.add(user)
    db.flush()
    user_id = user.id
    db.commit()
    db.rollback()
    return user_id


def _run_parallel(session_factory, user_id, fns):
    barrier = threading.Barrier(len(fns))

    def worker(fn):
        with session_factory() as session:
            user = session.get(User, user_id)
            barrier.wait(timeout=15)
            try:
                return ("ok", fn(session, user))
            except HTTPException as exc:
                return ("http", exc.status_code)

    with ThreadPoolExecutor(max_workers=len(fns)) as pool:
        return list(pool.map(worker, fns))


def test_concurrent_creates_with_the_same_name_produce_exactly_one_account(db_session, session_factory):
    user_id = _make_user(db_session)
    variants = ["Wallet", "wallet", "WALLET", " wallet ", "Wallet", "wAlLeT"]
    jobs = [
        (lambda session, user, name=name: financial_account_service.create_account(
            session, user, AccountCreate(name=name, kind="wallet", opening_balance=Decimal("5"))))
        for name in variants
    ]
    results = _run_parallel(session_factory, user_id, jobs)

    assert [r[0] for r in results].count("ok") == 1, results
    assert [r for r in results if r[0] == "http"] == [("http", 409)] * 5
    db_session.expire_all()
    assert db_session.query(FinancialAccount).count() == 1
    assert db_session.query(AccountBalanceSnapshot).count() == 1  # لقطة الحساب الفائز فقط، ما في لقطات يتيمة من الخاسرين


def test_delete_and_snapshot_race_never_loses_or_orphans_data(db_session, session_factory):
    """حذف حساب فاضي + لقطة عليه بنفس اللحظة: إما انحذف الحساب (واللقطة 404)، أو انقبلت اللقطة (والحذف 409)."""
    user_id = _make_user(db_session, "0790097102")
    with session_factory() as session:
        user = session.get(User, user_id)
        account_id = financial_account_service.create_account(session, user, AccountCreate(name="سباق", kind="cash")).id

    delete = lambda session, user: financial_account_service.delete_account(session, user, account_id)
    snapshot = lambda session, user: financial_account_service.add_balance_snapshot(
        session, user, account_id, BalanceSnapshotCreate(amount=Decimal("12")))
    delete_result, snapshot_result = _run_parallel(session_factory, user_id, [delete, snapshot])

    db_session.expire_all()
    account_exists = db_session.get(FinancialAccount, account_id) is not None
    snapshots = db_session.query(AccountBalanceSnapshot).filter(AccountBalanceSnapshot.account_id == account_id).count()
    if account_exists:
        assert delete_result == ("http", 409) and snapshot_result[0] == "ok" and snapshots == 1
    else:
        assert delete_result == ("ok", None) and snapshot_result == ("http", 404) and snapshots == 0


def test_concurrent_snapshots_are_all_kept_and_the_latest_as_of_wins(db_session, session_factory):
    user_id = _make_user(db_session, "0790097103")
    with session_factory() as session:
        user = session.get(User, user_id)
        account_id = financial_account_service.create_account(session, user, AccountCreate(name="لقطات", kind="bank")).id

    base = datetime.now(timezone.utc) - timedelta(hours=2)
    jobs = [
        (lambda session, user, i=i: financial_account_service.add_balance_snapshot(
            session, user, account_id,
            BalanceSnapshotCreate(amount=Decimal(i * 10), as_of=base + timedelta(minutes=i))))
        for i in range(10)
    ]
    results = _run_parallel(session_factory, user_id, jobs)

    assert all(r[0] == "ok" for r in results), results
    db_session.expire_all()
    assert db_session.query(AccountBalanceSnapshot).filter(AccountBalanceSnapshot.account_id == account_id).count() == 10
    with session_factory() as session:
        final = financial_account_service.get_account(session, session.get(User, user_id), account_id)
    assert final.balance == 90.0 and final.balance_quality == "manual_confirmed"  # آخر as_of (i=9) بغض النظر عن ترتيب الوصول
