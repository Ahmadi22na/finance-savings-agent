"""
بوابة سجل حركة الأهداف — الدفعة 0.C.

القاعدة: ما حدا بيعدّل goals.current_amount مباشرة. كل تغيير بيمر من record() هون،
فبيتكتب سطر بـ goal_movements بنفس اللحظة، وبنفس الـ transaction (الـ commit مسؤولية المستدعي).
القفل: lock_goals() بتقفل صفوف الأهداف FOR UPDATE بترتيب id ثابت (ما بيصير deadlock بين طلبين بأهداف مشتركة)،
و populate_existing() بتجبر قراءة القيم الحالية من القاعدة (مش نسخة قديمة بالـ session).
"""
import uuid
from decimal import Decimal
from enum import Enum

from sqlalchemy.orm import Session

from app.core.money import to_money
from app.models.goal import Goal
from app.models.goal_movement import GoalMovement


class MovementKind(str, Enum):
    OPENING = "opening"                          # رصيد افتتاحي عند الترحيل
    ALLOCATION = "allocation"                    # توزيع دخل
    MANUAL_CONTRIBUTION = "manual_contribution"  # مساهمة يدوية
    AGENT_CONTRIBUTION = "agent_contribution"    # موافقة على اقتراح رشيد
    REVERSAL = "reversal"                        # عكس (حذف/تعديل دخل) — الدفعة 0.D
    CYCLE_RESET = "cycle_reset"                  # تصفير بداية دورة هدف متكرر


def cycle_of(goal: Goal) -> str | None:
    """دورة الهدف الحالية: "YYYY-MM" للمتكرر، NULL لغير المتكرر."""
    return goal.last_reset_month if goal.is_recurring else None


def lock_goals(db: Session, user_id: uuid.UUID, goal_ids: list[uuid.UUID]) -> dict[uuid.UUID, Goal]:
    """يقفل أهداف المستخدم FOR UPDATE بترتيب id ثابت ويرجّعها بقيمها الحالية من القاعدة."""
    if not goal_ids:
        return {}
    goals = (
        db.query(Goal)
        .filter(Goal.user_id == user_id, Goal.id.in_(goal_ids))
        .order_by(Goal.id)
        .populate_existing()
        .with_for_update()
        .all()
    )
    return {goal.id: goal for goal in goals}


def record(
    db: Session,
    goal: Goal,
    amount: Decimal,
    kind: MovementKind,
    transaction_id: uuid.UUID | None = None,
) -> GoalMovement:
    """يطبّق حركة موقّعة على الهدف (الهدف لازم يكون مقفولاً من المستدعي) ويكتب سطرها. بدون commit."""
    amount = to_money(amount)
    movement = GoalMovement(
        goal_id=goal.id,
        amount=amount,
        kind=kind.value,
        transaction_id=transaction_id,
        cycle=cycle_of(goal),
    )
    goal.current_amount = to_money(goal.current_amount or 0) + amount
    db.add(movement)
    return movement
