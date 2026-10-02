"""Module documentation."""
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



ROUNDING_TOLERANCE = 0.01


def get_allocated_amount(db: Session, transaction_id: uuid.UUID) -> float:
    total = (
        db.query(func.coalesce(func.sum(IncomeAllocation.amount), 0))
        .filter(IncomeAllocation.transaction_id == transaction_id)
        .scalar()
    )
    return float(total or 0)


def get_unallocated_amount(db: Session, transaction: Transaction) -> float:
    """Get unallocated amount documentation."""
    if transaction.type != TransactionType.INCOME:
        return 0.0
    return max(0.0, float(transaction.amount) - get_allocated_amount(db, transaction.id))


def unallocated_amounts_for(db: Session, transactions: list[Transaction]) -> dict[uuid.UUID, float]:
    """Unallocated amounts for documentation."""
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

    requested_total = sum(item.amount for item in data.allocations)
    already_allocated = get_allocated_amount(db, transaction.id)
    available = float(transaction.amount) - already_allocated
    if requested_total > available + ROUNDING_TOLERANCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"المبلغ المطلوب توزيعه ({requested_total}) أكبر من المتاح فعليًا من هذا الدخل ({available:.2f})",
        )

    updated_goals = []
    leftover_unallocated = 0.0
    for item in data.allocations:
        goal = goals_by_id[item.goal_id]



        remaining_capacity = float(goal.target_amount) - float(goal.current_amount)
        amount_to_apply = min(item.amount, remaining_capacity)
        leftover_unallocated += item.amount - amount_to_apply

        if amount_to_apply <= 0:
            continue



        goal = goal_service.contribute_to_goal(
            db, user, item.goal_id, GoalContribution(amount=amount_to_apply)
        )
        db.add(IncomeAllocation(transaction_id=transaction.id, goal_id=goal.id, amount=amount_to_apply))
        updated_goals.append(goal)

    db.commit()
    db.refresh(transaction)
    return transaction, updated_goals
