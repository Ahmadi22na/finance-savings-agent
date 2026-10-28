"""
المرحلة 1 / الدفعة 1.B — التزامن والذرّية على PostgreSQL. كل اختبار بيتحقق من الحالة النهائية بالقاعدة، مش من نجاح الطلبات فقط.
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from app.models.financial_account import FinancialAccount
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.financial_account import AccountCreate
from app.schemas.transaction import TransactionQuickLogCreate, TransactionUpdate
from app.schemas.transfer import TransferCreate
from app.services import (
    financial_account_service,
    transaction_edit_service,
    transaction_service,
    transfer_service,
)


def _later():
    return datetime.now(timezone.utc) + timedelta(minutes=1)


def _make_accounts(session_factory, user_id, names, opening=Decimal("100")):
    with session_factory() as session:
        user = session.get(User, user_id)
        return [
            financial_account_service.create_account(session, user, AccountCreate(name=n, kind="cash", opening_balance=opening)).id
            for n in names
        ]


def _make_user(db, phone):
    user = User(name="pg transfers", phone=phone, hashed_password="x")
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


def _balance(session_factory, user_id, account_id):
    with session_factory() as session:
        return financial_account_service.get_account(session, session.get(User, user_id), account_id).balance


def _legs(db, user_id):
    db.expire_all()
    return db.query(Transaction).filter(Transaction.user_id == user_id, Transaction.is_transfer.is_(True)).all()


def test_failure_between_the_two_legs_leaves_no_leg_behind(db_session, session_factory, monkeypatch):
    user_id = _make_user(db_session, "0790097201")
    first, second = _make_accounts(session_factory, user_id, ["أ", "ب"])

    real = transfer_service.Transaction
    calls = {"count": 0}

    def flaky(**kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("فشل مصطنع بين الطرفين")
        return real(**kwargs)

    monkeypatch.setattr(transfer_service, "Transaction", flaky)
    with session_factory() as session:
        try:
            transfer_service.create_transfer(
                session, session.get(User, user_id),
                TransferCreate(from_account_id=first, to_account_id=second, amount=Decimal("5"), occurred_at=_later()),
            )
            raise AssertionError("كان لازم يفشل")
        except RuntimeError:
            pass

    assert _legs(db_session, user_id) == []                      # ولا طرف ضل (الطرف الأول انعمله flush وانعمله rollback)
    assert _balance(session_factory, user_id, first) == 100 and _balance(session_factory, user_id, second) == 100


def test_opposite_concurrent_transfers_neither_deadlock_nor_unbalance(db_session, session_factory):
    user_id = _make_user(db_session, "0790097202")
    first, second = _make_accounts(session_factory, user_id, ["أ", "ب"])

    def transfer(source, target, amount):
        return lambda session, user: transfer_service.create_transfer(
            session, user, TransferCreate(from_account_id=source, to_account_id=target, amount=amount, occurred_at=_later()))

    jobs = [transfer(first, second, Decimal("7")) if i % 2 == 0 else transfer(second, first, Decimal("3")) for i in range(8)]
    results = _run_parallel(session_factory, user_id, jobs)

    assert all(r[0] == "ok" for r in results), results
    legs = _legs(db_session, user_id)
    assert len(legs) == 16
    groups = {}
    for leg in legs:
        groups.setdefault(leg.transfer_group_id, []).append(leg)
    assert len(groups) == 8 and all(len(pair) == 2 for pair in groups.values())      # كل تحويل بطرفين بالضبط
    for pair in groups.values():
        assert {leg.type.value for leg in pair} == {"expense", "income"} and pair[0].amount == pair[1].amount
    # 4 تحويلات × 7 من الأول للثاني، و4 × 3 بالعكس: الأول -16، الثاني +16 — والمجموع ثابت
    assert _balance(session_factory, user_id, first) == 84 and _balance(session_factory, user_id, second) == 116


def test_linking_a_transaction_and_deleting_the_account_never_leave_a_dangling_link(db_session, session_factory):
    user_id = _make_user(db_session, "0790097203")
    with session_factory() as session:
        account_id = financial_account_service.create_account(
            session, session.get(User, user_id), AccountCreate(name="سباق", kind="cash")).id

    link = lambda session, user: transaction_service.create_quick_log_transaction(
        session, user, TransactionQuickLogCreate(amount=Decimal("1"), type="expense", note="x", account_id=account_id))
    delete = lambda session, user: financial_account_service.delete_account(session, user, account_id)
    link_result, delete_result = _run_parallel(session_factory, user_id, [link, delete])

    db_session.expire_all()
    account_exists = db_session.get(FinancialAccount, account_id) is not None
    linked = db_session.query(Transaction).filter(Transaction.account_id == account_id).count()
    if account_exists:   # الربط سبق: الحساب انحمى من الحذف
        assert link_result[0] == "ok" and delete_result == ("http", 409) and linked == 1
    else:                # الحذف سبق: الربط انرفض (404) وما ضل شي معلّق
        assert link_result == ("http", 404) and delete_result == ("ok", None) and linked == 0


def test_concurrent_edits_of_both_legs_always_end_with_equal_amounts(db_session, session_factory):
    user_id = _make_user(db_session, "0790097204")
    first, second = _make_accounts(session_factory, user_id, ["أ", "ب"])
    with session_factory() as session:
        transfer = transfer_service.create_transfer(
            session, session.get(User, user_id),
            TransferCreate(from_account_id=first, to_account_id=second, amount=Decimal("5"), occurred_at=_later()))

    edit = lambda leg_id, amount: (lambda session, user: transaction_edit_service.update_transaction(
        session, user, leg_id, TransactionUpdate(amount=Decimal(amount))))
    results = _run_parallel(session_factory, user_id, [
        edit(transfer.out_transaction_id, "7"), edit(transfer.in_transaction_id, "9"),
        edit(transfer.out_transaction_id, "11"), edit(transfer.in_transaction_id, "13"),
    ])

    assert all(r[0] == "ok" for r in results), results
    legs = _legs(db_session, user_id)
    assert len(legs) == 2 and legs[0].amount == legs[1].amount and legs[0].amount in {7, 9, 11, 13}   # ما في تحويل غير متوازن
    final = legs[0].amount
    assert _balance(session_factory, user_id, first) == 100 - final and _balance(session_factory, user_id, second) == 100 + final


def test_editing_and_deleting_a_transfer_at_the_same_time_never_leaves_half_a_transfer(db_session, session_factory):
    user_id = _make_user(db_session, "0790097205")
    first, second = _make_accounts(session_factory, user_id, ["أ", "ب"])
    with session_factory() as session:
        transfer = transfer_service.create_transfer(
            session, session.get(User, user_id),
            TransferCreate(from_account_id=first, to_account_id=second, amount=Decimal("5"), occurred_at=_later()))

    edit = lambda session, user: transaction_edit_service.update_transaction(
        session, user, transfer.out_transaction_id, TransactionUpdate(amount=Decimal("8")))
    delete = lambda session, user: transaction_edit_service.delete_transaction(session, user, transfer.in_transaction_id)
    edit_result, delete_result = _run_parallel(session_factory, user_id, [edit, delete])

    assert delete_result == ("ok", None) and edit_result[0] in {"ok", "http"}
    assert _legs(db_session, user_id) == []                              # الحذف دايمًا بيزيل الطرفين، مهما كان الترتيب
    assert _balance(session_factory, user_id, first) == 100 and _balance(session_factory, user_id, second) == 100
