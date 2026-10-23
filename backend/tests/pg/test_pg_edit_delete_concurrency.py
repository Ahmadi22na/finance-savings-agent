"""
الدفعة 0.D — تعديل/حذف دخل بالتزامن مع توزيع عليه (PostgreSQL حقيقي).
القفل FOR UPDATE على صف المعاملة بيخلّي النتيجة دايمًا واحدة من ترتيبين سليمين، مش حالة وسطية مكسورة.
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func

from app.models.goal import Goal
from app.models.goal_movement import GoalMovement
from app.models.income_allocation import IncomeAllocation
from app.models.transaction import Transaction, TransactionSource, TransactionType
from app.models.user import User
from app.schemas.transaction import IncomeAllocationItem, IncomeAllocationRequest, TransactionUpdate
from app.services import income_allocation_service, transaction_edit_service


def _setup(db):
    user = User(name="pg edit", phone="0790097002", hashed_password="x")
    db.add(user)
    db.flush()
    user_id = user.id
    goal = Goal(user_id=user_id, title="هدف", target_amount=Decimal("1000"), current_amount=0)
    income = Transaction(user_id=user_id, amount=Decimal("100"), type=TransactionType.INCOME,
                         source=TransactionSource.MANUAL, occurred_at=datetime.now(timezone.utc))
    db.add_all([goal, income])
    db.flush()
    ids = (user_id, goal.id, income.id)
    db.commit()
    db.rollback()
    return ids


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


def _allocate(goal_id, income_id, amount):
    request = IncomeAllocationRequest(allocations=[IncomeAllocationItem(goal_id=goal_id, amount=amount)])
    return lambda session, user: income_allocation_service.allocate_income(session, user, income_id, request)


def test_allocation_and_amount_edit_cannot_both_win(db_session, session_factory):
    """توزيع 60 + خفض المبلغ لـ 50 بنفس اللحظة: لازم واحد بس ينجح (مهما كان الترتيب)، ولا يصير موزَّع 60 من دخل 50."""
    user_id, goal_id, income_id = _setup(db_session)
    edit = lambda session, user: transaction_edit_service.update_transaction(
        session, user, income_id, TransactionUpdate(amount=Decimal("50")))
    results = _run_parallel(session_factory, user_id, [_allocate(goal_id, income_id, Decimal("60")), edit])

    assert sorted(r[0] for r in results) == ["http", "ok"], results
    db_session.expire_all()
    amount = Decimal(db_session.get(Transaction, income_id).amount)
    allocated = Decimal(db_session.query(func.coalesce(func.sum(IncomeAllocation.amount), 0)).scalar())
    assert allocated <= amount


def test_delete_and_allocation_end_in_a_consistent_state(db_session, session_factory):
    """حذف الدخل + توزيع عليه بنفس اللحظة: بالنهاية المعاملة محذوفة، والهدف 0، والسجل متطابق."""
    user_id, goal_id, income_id = _setup(db_session)
    delete = lambda session, user: transaction_edit_service.delete_transaction(session, user, income_id)
    results = _run_parallel(session_factory, user_id, [_allocate(goal_id, income_id, Decimal("60")), delete])

    assert ("ok", None) in results, results
    db_session.expire_all()
    assert db_session.get(Transaction, income_id) is None
    assert Decimal(db_session.get(Goal, goal_id).current_amount) == 0
    assert db_session.query(IncomeAllocation).count() == 0
    moved = db_session.query(func.coalesce(func.sum(GoalMovement.amount), 0)).filter(GoalMovement.goal_id == goal_id).scalar()
    assert Decimal(moved) == 0
