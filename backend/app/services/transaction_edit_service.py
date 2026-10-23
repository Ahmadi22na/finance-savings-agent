"""
تعديل وحذف المعاملات مع الحفاظ على سلامة التوزيعات والأهداف — الدفعة 0.D.

قواعد:
- كل عملية بقفل صف المعاملة FOR UPDATE وcommit واحد (كله أو ولا شي)؛ تعديل/حذف دخل بيتسلسل مع أي توزيع متزامن عليه.
- دخل موزَّع: ما بنقبل مبلغًا أقل من الموزَّع منه. وحذفه بيعكس التوزيعات بحركات REVERSAL بسجل الأهداف.
- قاعدة الدورة: عكس توزيع ما بيمس مبلغ الهدف إلا لو التوزيع من دورة الهدف الحالية (هدف متكرر انصفّر بشهر جديد
  بيضل مبلغه الحالي كما هو لو انحذف دخل شهر سابق). والمبلغ ما بينزل تحت الصفر أبدًا.
- توزيعات قديمة (قبل 0.C) ما إلها حركة بالسجل: بنعتبرها من الدورة الحالية فقط للهدف غير المتكرر.
"""
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.money import to_money
from app.models.goal import GoalStatus
from app.models.goal_movement import GoalMovement
from app.models.income_allocation import IncomeAllocation
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.transaction import TransactionUpdate
from app.services import goal_ledger, goal_service, income_allocation_service, transaction_service
from app.services.goal_ledger import MovementKind

ZERO = Decimal("0.000")


def update_transaction(db: Session, user: User, transaction_id: uuid.UUID, data: TransactionUpdate) -> Transaction:
    fields = data.model_fields_set
    try:
        transaction = income_allocation_service.lock_transaction_or_404(db, user, transaction_id)

        if "amount" in fields:
            new_amount = to_money(data.amount)
            if transaction.type == TransactionType.INCOME:
                allocated = income_allocation_service.get_allocated_amount(db, transaction.id)
                if new_amount < allocated:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"المبلغ الجديد ({new_amount:.3f}) أقل من المبلغ الموزَّع على أهدافك ({allocated:.3f}). "
                            "احذف المعاملة لعكس التوزيع ثم سجّلها من جديد"
                        ),
                    )
            transaction.amount = new_amount

        if "occurred_at" in fields:
            transaction.occurred_at = data.occurred_at

        if "note" in fields:
            transaction.note = (data.note or "").strip() or None

        if "category_id" in fields:
            transaction_service.set_category(db, user, transaction, data.category_id)

        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, user: User, transaction_id: uuid.UUID) -> None:
    try:
        transaction = income_allocation_service.lock_transaction_or_404(db, user, transaction_id)

        if transaction.type == TransactionType.INCOME:
            _reverse_allocations(db, user, transaction)

        db.flush()  # حركات العكس لازم تنكتب قبل ما نفصل ربطها بالمعاملة
        db.query(GoalMovement).filter(GoalMovement.transaction_id == transaction.id).update(
            {GoalMovement.transaction_id: None}, synchronize_session=False
        )
        db.query(IncomeAllocation).filter(IncomeAllocation.transaction_id == transaction.id).delete(
            synchronize_session=False
        )
        db.delete(transaction)
        db.commit()
    except Exception:
        db.rollback()
        raise


def _reverse_allocations(db: Session, user: User, transaction: Transaction) -> None:
    allocations = db.query(IncomeAllocation).filter(IncomeAllocation.transaction_id == transaction.id).all()
    if not allocations:
        return

    goals = goal_ledger.lock_goals(db, user.id, sorted({a.goal_id for a in allocations}))
    for goal in goals.values():
        goal_service.apply_recurring_reset_if_needed(db, goal)  # دورة الهدف الحالية لازم تكون محدّثة قبل المقارنة

    for goal_id, goal in goals.items():
        allocated_total = sum((to_money(a.amount) for a in allocations if a.goal_id == goal_id), ZERO)
        movements = (
            db.query(GoalMovement)
            .filter(
                GoalMovement.goal_id == goal_id,
                GoalMovement.transaction_id == transaction.id,
                GoalMovement.kind == MovementKind.ALLOCATION.value,
            )
            .all()
        )
        moved_total = sum((to_money(m.amount) for m in movements), ZERO)
        moved_same_cycle = sum(
            (to_money(m.amount) for m in movements if m.cycle == goal_ledger.cycle_of(goal)), ZERO
        )
        legacy_without_movement = max(ZERO, allocated_total - moved_total)

        reversible = moved_same_cycle + (legacy_without_movement if not goal.is_recurring else ZERO)
        reversible = min(reversible, max(to_money(goal.current_amount), ZERO))  # ما بننزل تحت الصفر

        if reversible > 0:
            goal_ledger.record(db, goal, -reversible, MovementKind.REVERSAL, transaction_id=transaction.id)
            if goal.status == GoalStatus.ACHIEVED and to_money(goal.current_amount) < to_money(goal.target_amount):
                goal.status = GoalStatus.ACTIVE
