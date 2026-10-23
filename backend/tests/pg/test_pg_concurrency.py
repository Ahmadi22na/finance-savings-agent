"""
الدفعة 0.C — التزامن الحقيقي على PostgreSQL (جلسة + اتصال لكل thread).
بدون القفل FOR UPDATE: الاختبار الأول كان بيسمح بتجاوز المتاح، والثاني بيضيّع تحديثات، والثالث ممكن يعمل deadlock.
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func

from app.models.goal import Goal
from app.models.goal_movement import GoalMovement
from app.models.income_allocation import IncomeAllocation
from app.models.transaction import Transaction, TransactionSource, TransactionType
from app.models.user import User
from app.schemas.goal import GoalContribution
from app.schemas.transaction import IncomeAllocationItem, IncomeAllocationRequest
from app.services import goal_service, income_allocation_service
from datetime import datetime, timezone


def _setup(db, goal_count=2, incomes=(100,)):
    """بيجهّز البيانات ويرجّع الـ ids كقيم عادية. ما بنقرا خصائص الكائنات بعد commit
    (كانت تفتح transaction جديدة بجلسة الاختبار وتتركها مفتوحة وتعلّق أوامر DROP لاحقًا)."""
    user = User(name="pg concurrency", phone="0790097001", hashed_password="x")
    db.add(user)
    db.flush()
    user_id = user.id
    goals = [Goal(user_id=user_id, title=f"هدف {i}", target_amount=Decimal("1000"), current_amount=0) for i in range(goal_count)]
    txs = [
        Transaction(user_id=user_id, amount=Decimal(a), type=TransactionType.INCOME,
                    source=TransactionSource.MANUAL, occurred_at=datetime.now(timezone.utc))
        for a in incomes
    ]
    db.add_all(goals + txs)
    db.flush()
    goal_ids = [g.id for g in goals]
    tx_ids = [t.id for t in txs]
    db.commit()
    return user_id, goal_ids, tx_ids


def _run_parallel(session_factory, jobs):
    """يشغّل كل job بـ thread وجلسة خاصة، وبيبدأوا مع بعض (Barrier)."""
    barrier = threading.Barrier(len(jobs))

    def worker(job):
        with session_factory() as session:
            user = session.get(User, job["user_id"])
            barrier.wait(timeout=15)
            try:
                return ("ok", job["fn"](session, user))
            except HTTPException as exc:
                return ("http", exc.status_code)

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(worker, jobs))


def _alloc(goal_amounts, tx_id):
    request = IncomeAllocationRequest(allocations=[IncomeAllocationItem(goal_id=g, amount=a) for g, a in goal_amounts])
    return lambda session, user: income_allocation_service.allocate_income(session, user, tx_id, request)


def _assert_consistent(db):
    db.expire_all()
    for goal in db.query(Goal).all():
        moved = db.query(func.coalesce(func.sum(GoalMovement.amount), 0)).filter(GoalMovement.goal_id == goal.id).scalar()
        assert Decimal(goal.current_amount) == Decimal(moved), goal.title


def test_two_allocations_on_the_same_income_cannot_exceed_it(db_session, session_factory):
    user_id, goals, [income] = _setup(db_session, goal_count=2, incomes=(100,))
    db_session.rollback()
    jobs = [
        {"user_id": user_id, "fn": _alloc([(goals[0], Decimal("60"))], income)},
        {"user_id": user_id, "fn": _alloc([(goals[1], Decimal("60"))], income)},
    ]
    results = _run_parallel(session_factory, jobs)

    assert sorted(r[0] for r in results) == ["http", "ok"], results
    db_session.expire_all()
    allocated = db_session.query(func.sum(IncomeAllocation.amount)).scalar()
    assert Decimal(allocated) == Decimal("60")
    _assert_consistent(db_session)


def test_concurrent_contributions_lose_no_update(db_session, session_factory):
    user_id, [goal], _ = _setup(db_session, goal_count=1, incomes=())
    data = GoalContribution(amount=Decimal("1"))
    jobs = [
        {"user_id": user_id, "fn": lambda session, user: goal_service.contribute_to_goal(session, user, goal, data)}
        for _ in range(10)
    ]
    results = _run_parallel(session_factory, jobs)

    assert all(r[0] == "ok" for r in results), results
    db_session.expire_all()
    assert Decimal(db_session.get(Goal, goal).current_amount) == Decimal("10")
    assert db_session.query(GoalMovement).filter(GoalMovement.goal_id == goal).count() == 10
    _assert_consistent(db_session)


def test_allocations_in_opposite_goal_orders_do_not_deadlock(db_session, session_factory):
    user_id, goals, incomes = _setup(db_session, goal_count=2, incomes=(100,) * 8)
    jobs = []
    for index, income in enumerate(incomes):
        order = goals if index % 2 == 0 else list(reversed(goals))
        jobs.append({"user_id": user_id, "fn": _alloc([(order[0], Decimal("10")), (order[1], Decimal("10"))], income)})
    results = _run_parallel(session_factory, jobs)

    assert all(r[0] == "ok" for r in results), results
    db_session.expire_all()
    for goal in goals:
        assert Decimal(db_session.get(Goal, goal).current_amount) == Decimal("80")
    _assert_consistent(db_session)
