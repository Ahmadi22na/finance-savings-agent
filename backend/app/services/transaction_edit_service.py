"""
تعديل وحذف المعاملات مع الحفاظ على سلامة التوزيعات والأهداف والتحويلات — الدفعة 0.D + 1.B.

قواعد:
- كل عملية بقفل صف المعاملة FOR UPDATE وcommit واحد (كله أو ولا شي)؛ تعديل/حذف دخل بيتسلسل مع أي توزيع متزامن عليه.
- دخل موزَّع: ما بنقبل مبلغًا أقل من الموزَّع منه. وحذفه بيعكس التوزيعات بحركات REVERSAL بسجل الأهداف.
- قاعدة الدورة: عكس توزيع ما بيمس مبلغ الهدف إلا لو التوزيع من دورة الهدف الحالية (هدف متكرر انصفّر بشهر جديد
  بيضل مبلغه الحالي كما هو لو انحذف دخل شهر سابق). والمبلغ ما بينزل تحت الصفر أبدًا.
- توزيعات قديمة (قبل 0.C) ما إلها حركة بالسجل: بنعتبرها من الدورة الحالية فقط للهدف غير المتكرر.
- (1.B) طرف تحويل داخلي: بنقفل الطرفين سوا (بترتيب id ثابت)، والمبلغ/التاريخ/الملاحظة بتتعدّل على الطرفين، والحذف
  بيحذف الطرفين، والتصنيف وتغيير الحساب مرفوضين. فما بيصير تحويل غير متوازن أبدًا.
- (1.B) ربط/نقل معاملة عادية لحساب: حساب نشط يخص المستخدم (قفل مشترك)، أو null لفك الربط.
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
from app.services import (
    financial_account_service,
    goal_ledger,
    goal_service,
    income_allocation_service,
    transaction_service,
)
from app.services.goal_ledger import MovementKind

ZERO = Decimal("0.000")


def _lock_target(db: Session, user: User, transaction_id: uuid.UUID) -> tuple[Transaction, list[Transaction]]:
    """
    يقفل المعاملة (وطرفي التحويل سوا لو كانت تحويل) ويرجّع (المعاملة، كل أطراف مجموعتها).
    بنقرأ المجموعة أول (بدون قفل) وبعدين بنقفل كل الأطراف بترتيب id واحد: طلبان متزامنان على طرفين مختلفين من نفس
    التحويل ما بيعملوا deadlock، وما بيتعدّل طرف لحاله.
    """
    probe = (
        db.query(Transaction.is_transfer, Transaction.transfer_group_id)
        .filter(Transaction.id == transaction_id, Transaction.user_id == user.id)
        .first()
    )
    if probe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المعاملة غير موجودة")

    if not probe.is_transfer:
        transaction = income_allocation_service.lock_transaction_or_404(db, user, transaction_id)
        return transaction, [transaction]

    legs = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id, Transaction.transfer_group_id == probe.transfer_group_id)
        .order_by(Transaction.id)
        .populate_existing()
        .with_for_update()
        .all()
    )
    transaction = next((leg for leg in legs if leg.id == transaction_id), None)
    if transaction is None:  # انحذف بين القراءة والقفل
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المعاملة غير موجودة")
    return transaction, legs


def update_transaction(db: Session, user: User, transaction_id: uuid.UUID, data: TransactionUpdate) -> Transaction:
    fields = data.model_fields_set
    try:
        transaction, legs = _lock_target(db, user, transaction_id)

        if transaction.is_transfer:
            if "category_id" in fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="طرف التحويل بين الحسابات ما بيحمل تصنيف"
                )
            if "account_id" in fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ما بتقدر تغيّر حساب طرف تحويل. احذف التحويل وأنشئه من جديد",
                )

        if "amount" in fields:
            new_amount = to_money(data.amount)
            if transaction.type == TransactionType.INCOME and not transaction.is_transfer:
                allocated = income_allocation_service.get_allocated_amount(db, transaction.id)
                if new_amount < allocated:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"المبلغ الجديد ({new_amount:.3f}) أقل من المبلغ الموزَّع على أهدافك ({allocated:.3f}). "
                            "احذف المعاملة لعكس التوزيع ثم سجّلها من جديد"
                        ),
                    )
            for leg in legs:  # لتحويل: الطرفين دايمًا بنفس المبلغ
                leg.amount = new_amount

        if "occurred_at" in fields:
            for leg in legs:
                leg.occurred_at = data.occurred_at

        if "note" in fields:
            new_note = (data.note or "").strip() or None
            for leg in legs:
                leg.note = new_note

        if "category_id" in fields:
            transaction_service.set_category(db, user, transaction, data.category_id)

        if "account_id" in fields and data.account_id != transaction.account_id:
            if data.account_id is None:
                transaction.account_id = None
            else:
                financial_account_service.lock_account_for_link(db, user, data.account_id)
                transaction.account_id = data.account_id

        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, user: User, transaction_id: uuid.UUID) -> None:
    try:
        transaction, legs = _lock_target(db, user, transaction_id)

        if transaction.is_transfer:
            for leg in legs:  # الطرفين سوا، دايمًا
                db.delete(leg)
            db.commit()
            return

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
