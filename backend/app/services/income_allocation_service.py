"""
Income Allocation Service — Sprint 7 جزء (ج).

القرار المعتمد من أحمد: التوزيع دايمًا يسأل المستخدم صراحة (ما في auto-route
تلقائي لأعلى أولوية) — هالملف بس ينفذ التوزيع بعد ما المستخدم يحدد بنفسه
وين بدو يحط كل جزء من الدخل، ما بيقترح شي من عنده.

الدفعة 0.B: كل الحسابات بـ Decimal بدقة 3 خانات (فلس) عبر app.core.money،
والقيم بترجع Decimal — الـ routes هي اللي بتحوّلها لـ float بمخرجات الـ API.
"""
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.money import MONEY_DECIMALS, to_money  # noqa: F401  (MONEY_DECIMALS يبقى متاح من هون)
from app.models.goal import Goal, GoalStatus
from app.models.income_allocation import IncomeAllocation
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.transaction import IncomeAllocationRequest
from app.services import goal_ledger, goal_service
from app.services.goal_ledger import MovementKind

ZERO = Decimal("0.000")


def get_allocated_amount(db: Session, transaction_id: uuid.UUID) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(IncomeAllocation.amount), 0))
        .filter(IncomeAllocation.transaction_id == transaction_id)
        .scalar()
    )
    return to_money(total or 0)


def get_unallocated_amount(db: Session, transaction: Transaction) -> Decimal:
    """0 دايمًا لمعاملات المصروف وأطراف التحويل الداخلي — مفهوم التوزيع خاص بالدخل الحقيقي بس."""
    if transaction.type != TransactionType.INCOME or transaction.is_transfer:
        return ZERO
    return max(ZERO, to_money(transaction.amount) - get_allocated_amount(db, transaction.id))


def unallocated_amounts_for(db: Session, transactions: list[Transaction]) -> dict[uuid.UUID, Decimal]:
    """
    نفس get_unallocated_amount بس لقائمة كاملة بطلب SQL واحد (GROUP BY) بدل
    طلب لكل معاملة — مهم لأن الداشبورد صار يجيب حتى 100 معاملة عشان بانر
    "دخل بانتظار التوزيع" (استيراد الرسائل ممكن يضيف عشرات الدخول دفعة وحدة).
    المفتاح: id المعاملة، بس لمعاملات الدخل — المصروف مش موجود بالنتيجة (= 0).
    """
    income_ids = [t.id for t in transactions if t.type == TransactionType.INCOME and not t.is_transfer]
    if not income_ids:
        return {}

    rows = (
        db.query(IncomeAllocation.transaction_id, func.coalesce(func.sum(IncomeAllocation.amount), 0))
        .filter(IncomeAllocation.transaction_id.in_(income_ids))
        .group_by(IncomeAllocation.transaction_id)
        .all()
    )
    allocated = {transaction_id: to_money(total) for transaction_id, total in rows}
    return {
        t.id: max(ZERO, to_money(t.amount) - allocated.get(t.id, ZERO))
        for t in transactions
        if t.type == TransactionType.INCOME and not t.is_transfer
    }


def lock_transaction_or_404(db: Session, user: User, transaction_id: uuid.UUID) -> Transaction:
    """يقفل صف الدخل FOR UPDATE: توزيعان متزامنان على نفس الدخل بيتسلسلوا بدل ما يتجاوزوا المتاح سوا."""
    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == user.id)
        .populate_existing()
        .with_for_update()
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المعاملة غير موجودة")
    return transaction


def allocate_income(
    db: Session, user: User, transaction_id: uuid.UUID, data: IncomeAllocationRequest
) -> tuple[Transaction, list[Goal]]:
    """
    كله أو ولا شي (الدفعة 0.C): قفل الدخل ثم الأهداف (بترتيب id ثابت)، كل الحركات بالسجل، وcommit واحد بالنهاية.
    أي فشل بنص التوزيع = rollback كامل (ما بيضل هدف مرفوع بدون سجل توزيع).
    """
    try:
        return _allocate_income_locked(db, user, transaction_id, data)
    except Exception:
        db.rollback()
        raise


def _allocate_income_locked(
    db: Session, user: User, transaction_id: uuid.UUID, data: IncomeAllocationRequest
) -> tuple[Transaction, list[Goal]]:
    transaction = lock_transaction_or_404(db, user, transaction_id)

    if transaction.is_transfer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="هاي حركة تحويل بين حساباتك مش دخل جديد، فما بتتوزع على الخطط",
        )

    if transaction.type != TransactionType.INCOME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="بس معاملات الدخل ممكن نوزعها على الخطط",
        )

    goal_ids = [item.goal_id for item in data.allocations]
    if len(set(goal_ids)) != len(goal_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ما بتقدر تكرر نفس الخطة أكتر من مرة بنفس التوزيع",
        )

    # نقفل الأهداف ونتحقق من كل شي (وجود الخطط، ملكيتها، إنها نشطة، والمجموع الكلي)
    # قبل ما نطبّق أي حركة — كله أو ولا شي.
    goals_by_id = goal_ledger.lock_goals(db, user.id, goal_ids)
    missing_ids = set(goal_ids) - set(goals_by_id.keys())
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="في خطة مش موجودة أو مش تبعتك بالتوزيع",
        )

    for goal in goals_by_id.values():
        goal_service.apply_recurring_reset_if_needed(db, goal)  # هدف متكرر منجز من شهر سابق بيرجع نشط

    not_active = [g for g in goals_by_id.values() if g.status != GoalStatus.ACTIVE]
    if not_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ما بتقدر توزع على خطة مو نشطة (منجزة أو متروكة)",
        )

    # المبالغ وصلت من الـ schema بحد أقصى 3 خانات (المدخلات الأكتر بتنرفض 422 قبل هون)
    amounts = [to_money(item.amount) for item in data.allocations]
    if any(amount <= 0 for amount in amounts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="كل مبلغ بالتوزيع لازم يكون 0.001 على الأقل",
        )

    requested_total = sum(amounts, ZERO)
    already_allocated = get_allocated_amount(db, transaction.id)
    available = to_money(transaction.amount) - already_allocated
    if requested_total > available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"المبلغ المطلوب توزيعه ({requested_total:.3f}) أكبر من المتاح فعليًا من هذا الدخل ({available:.3f})",
        )

    updated_goals = []
    leftover_unallocated = ZERO
    for item, amount in zip(data.allocations, amounts):
        goal = goals_by_id[item.goal_id]
        # الحد الأقصى يلي فعليًا محتاجه الهدف — ما بنسمح نعبّيه فوق سقفه.
        # أي جزء زايد عن الحاجة يضل "غير موزّع" على المعاملة (المستخدم قرر
        # وين يحطه لاحقًا)، مش بيضيع وبيصير current_amount غلط أكبر من الهدف.
        remaining_capacity = to_money(goal.target_amount) - to_money(goal.current_amount)
        amount_to_apply = min(amount, remaining_capacity)
        leftover_unallocated += amount - amount_to_apply

        if amount_to_apply <= 0:
            continue  # الهدف مكتفي فعليًا، تجاهل هالعنصر

        # نفس البوابة المستخدمة بالمساهمة اليدوية ومسار رشيد — مصدر وحيد للحقيقة
        goal_service.apply_contribution(
            db, user, goal.id, amount_to_apply, MovementKind.ALLOCATION,
            transaction_id=transaction.id, goal=goal,
        )
        db.add(IncomeAllocation(transaction_id=transaction.id, goal_id=goal.id, amount=amount_to_apply))
        updated_goals.append(goal)

    db.commit()
    db.refresh(transaction)
    for goal in updated_goals:
        db.refresh(goal)
    return transaction, updated_goals
