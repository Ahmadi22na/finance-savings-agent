"""
Income Allocation Service — Sprint 7 جزء (ج).

القرار المعتمد من أحمد: التوزيع دايمًا يسأل المستخدم صراحة (ما في auto-route
تلقائي لأعلى أولوية) — هالملف بس ينفذ التوزيع بعد ما المستخدم يحدد بنفسه
وين بدو يحط كل جزء من الدخل، ما بيقترح شي من عنده.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.goal import Goal, GoalStatus
from app.models.income_allocation import IncomeAllocation
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.goal import GoalContribution
from app.schemas.transaction import IncomeAllocationRequest
from app.services import goal_service, transaction_service

# المبالغ بتتخزّن بخانتين عشريتين (Numeric(12,2))، فكل مبلغ بنقرّبه لخانتين قبل أي مقارنة أو تطبيق.
# هيك أخطاء الفاصلة العائمة (مثل 0.1 + 0.2) ما بتأثر، وكمان مجموع التوزيع ما بيتجاوز الدخل ولا بمقدار 0.01.
MONEY_DECIMALS = 2


def get_allocated_amount(db: Session, transaction_id: uuid.UUID) -> float:
    total = (
        db.query(func.coalesce(func.sum(IncomeAllocation.amount), 0))
        .filter(IncomeAllocation.transaction_id == transaction_id)
        .scalar()
    )
    return float(total or 0)


def get_unallocated_amount(db: Session, transaction: Transaction) -> float:
    """0 دايمًا لمعاملات المصروف — مفهوم التوزيع خاص بالدخل بس."""
    if transaction.type != TransactionType.INCOME:
        return 0.0
    return max(0.0, float(transaction.amount) - get_allocated_amount(db, transaction.id))


def unallocated_amounts_for(db: Session, transactions: list[Transaction]) -> dict[uuid.UUID, float]:
    """
    نفس get_unallocated_amount بس لقائمة كاملة بطلب SQL واحد (GROUP BY) بدل
    طلب لكل معاملة — مهم لأن الداشبورد صار يجيب حتى 100 معاملة عشان بانر
    "دخل بانتظار التوزيع" (استيراد الرسائل ممكن يضيف عشرات الدخول دفعة وحدة).
    المفتاح: id المعاملة، بس لمعاملات الدخل — المصروف مش موجود بالنتيجة (= 0).
    """
    income_ids = [t.id for t in transactions if t.type == TransactionType.INCOME]
    if not income_ids:
        return {}

    rows = (
        db.query(IncomeAllocation.transaction_id, func.coalesce(func.sum(IncomeAllocation.amount), 0))
        .filter(IncomeAllocation.transaction_id.in_(income_ids))
        .group_by(IncomeAllocation.transaction_id)
        .all()
    )
    allocated = {transaction_id: float(total) for transaction_id, total in rows}
    return {
        t.id: max(0.0, float(t.amount) - allocated.get(t.id, 0.0))
        for t in transactions
        if t.type == TransactionType.INCOME
    }


def allocate_income(
    db: Session, user: User, transaction_id: uuid.UUID, data: IncomeAllocationRequest
) -> tuple[Transaction, list[Goal]]:
    transaction = transaction_service.get_transaction_or_404(db, user, transaction_id)

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

    # نتحقق من كل شي أول (وجود الخطط، ملكيتها، إنها نشطة، والمجموع الكلي)
    # قبل ما نطبّق أي مساهمة فعلية — عشان ما يصير توزيع جزئي لو فشل عنصر
    # بنص القائمة (نفس فلسفة reorder_goals: كل أو ولا شي).
    goals_by_id = {
        goal.id: goal
        for goal in db.query(Goal).filter(Goal.user_id == user.id, Goal.id.in_(goal_ids)).all()
    }
    missing_ids = set(goal_ids) - set(goals_by_id.keys())
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="في خطة مش موجودة أو مش تبعتك بالتوزيع",
        )

    not_active = [g for g in goals_by_id.values() if g.status != GoalStatus.ACTIVE]
    if not_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ما بتقدر توزع على خطة مو نشطة (منجزة أو متروكة)",
        )

    amounts = [round(item.amount, MONEY_DECIMALS) for item in data.allocations]
    if any(amount <= 0 for amount in amounts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="كل مبلغ بالتوزيع لازم يكون 0.01 على الأقل",
        )

    requested_total = round(sum(amounts), MONEY_DECIMALS)
    already_allocated = get_allocated_amount(db, transaction.id)
    available = round(float(transaction.amount) - already_allocated, MONEY_DECIMALS)
    if requested_total > available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"المبلغ المطلوب توزيعه ({requested_total:.2f}) أكبر من المتاح فعليًا من هذا الدخل ({available:.2f})",
        )

    updated_goals = []
    leftover_unallocated = 0.0
    for item, amount in zip(data.allocations, amounts):
        goal = goals_by_id[item.goal_id]
        # الحد الأقصى يلي فعليًا محتاجه الهدف — ما بنسمح نعبّيه فوق سقفه.
        # أي جزء زايد عن الحاجة يضل "غير موزّع" على المعاملة (المستخدم قرر
        # وين يحطه لاحقًا)، مش بيضيع وبيصير current_amount غلط أكبر من الهدف.
        remaining_capacity = round(float(goal.target_amount) - float(goal.current_amount), MONEY_DECIMALS)
        amount_to_apply = min(amount, remaining_capacity)
        leftover_unallocated += amount - amount_to_apply

        if amount_to_apply <= 0:
            continue  # الهدف مكتفي فعليًا (احتمال نادر: سباق تزامن)، تجاهل هالعنصر

        # contribute_to_goal هي نفس الدالة المستخدمة بالمساهمة اليدوية —
        # نفس منطق الوصول لـ ACHIEVED بالضبط، مصدر وحيد للحقيقة بدل ما نكرره هون
        goal = goal_service.contribute_to_goal(
            db, user, item.goal_id, GoalContribution(amount=amount_to_apply)
        )
        db.add(IncomeAllocation(transaction_id=transaction.id, goal_id=goal.id, amount=amount_to_apply))
        updated_goals.append(goal)

    db.commit()
    db.refresh(transaction)
    return transaction, updated_goals
