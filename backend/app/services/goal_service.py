import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.goal import Goal, GoalStatus
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalContribution


def create_goal(db: Session, user: User, data: GoalCreate) -> Goal:
    goal = Goal(
        user_id=user.id,
        title=data.title,
        icon=data.icon,
        target_amount=data.target_amount,
        deadline=data.deadline,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def list_goals_for_user(db: Session, user: User) -> list[Goal]:
    return (
        db.query(Goal)
        .filter(Goal.user_id == user.id)
        .order_by(Goal.status, Goal.created_at.desc())
        .all()
    )


def get_goal_or_404(db: Session, user: User, goal_id: uuid.UUID) -> Goal:
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الهدف غير موجود")
    return goal


def contribute_to_goal(db: Session, user: User, goal_id: uuid.UUID, data: GoalContribution) -> Goal:
    goal = get_goal_or_404(db, user, goal_id)

    if goal.status != GoalStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ما بتقدر تضيف مبلغ لهدف مو نشط (منجز أو متروك)",
        )

    goal.current_amount = float(goal.current_amount) + data.amount

    if float(goal.current_amount) >= float(goal.target_amount):
        goal.status = GoalStatus.ACHIEVED

    db.commit()
    db.refresh(goal)
    return goal


def delete_goal(db: Session, user: User, goal_id: uuid.UUID) -> None:
    """
    حذف نهائي للهدف. ما بيلمس المعاملات المالية المرتبطة (Transactions) —
    هاي بتضل موجودة بسجل المستخدم، بس بتفقد ربطها بأي هدف (الأهداف والمعاملات
    مستقلتين أصلاً بالتصميم الحالي).
    """
    goal = get_goal_or_404(db, user, goal_id)
    db.delete(goal)
    db.commit()
