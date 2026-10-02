import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.goal import Goal, GoalStatus
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalContribution, GoalReorderRequest


def _current_month_key() -> str:
    return date.today().strftime("%Y-%m")


def _next_priority_for_user(db: Session, user: User) -> int:
    """ next priority for user documentation."""
    max_priority = (
        db.query(Goal.priority)
        .filter(Goal.user_id == user.id)
        .order_by(Goal.priority.desc())
        .limit(1)
        .scalar()
    )
    return (max_priority or 0) + 1


def _apply_recurring_reset_if_needed(goal: Goal) -> bool:
    """ apply recurring reset if needed documentation."""
    if not goal.is_recurring:
        return False

    current_month = _current_month_key()
    if goal.last_reset_month == current_month:
        return False

    if goal.status == GoalStatus.ACHIEVED:
        goal.current_amount = 0
        goal.status = GoalStatus.ACTIVE

    goal.last_reset_month = current_month
    return True


def create_goal(db: Session, user: User, data: GoalCreate) -> Goal:
    goal = Goal(
        user_id=user.id,
        title=data.title,
        icon=data.icon,
        target_amount=data.target_amount,
        deadline=data.deadline,
        priority=_next_priority_for_user(db, user),
        is_recurring=data.is_recurring,
        last_reset_month=_current_month_key() if data.is_recurring else None,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def list_goals_for_user(db: Session, user: User) -> list[Goal]:
    goals = (
        db.query(Goal)
        .filter(Goal.user_id == user.id)
        .order_by(Goal.status, Goal.priority, Goal.created_at.desc())
        .all()
    )

    any_changed = False
    for goal in goals:
        if _apply_recurring_reset_if_needed(goal):
            any_changed = True

    if any_changed:
        db.commit()



        return list_goals_for_user(db, user)

    return goals


def reorder_goals(db: Session, user: User, data: GoalReorderRequest) -> list[Goal]:
    """Reorder goals documentation."""
    active_goals = (
        db.query(Goal)
        .filter(Goal.user_id == user.id, Goal.status == GoalStatus.ACTIVE)
        .all()
    )
    active_by_id = {goal.id: goal for goal in active_goals}

    if set(data.ordered_goal_ids) != set(active_by_id.keys()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لازم ترسل كل الخطط النشطة الحالية بالترتيب الجديد، ولا وحدة أكتر أو أقل",
        )

    for index, goal_id in enumerate(data.ordered_goal_ids):
        active_by_id[goal_id].priority = index

    db.commit()
    return list_goals_for_user(db, user)


def get_goal_or_404(db: Session, user: User, goal_id: uuid.UUID) -> Goal:
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الهدف غير موجود")
    if _apply_recurring_reset_if_needed(goal):
        db.commit()
        db.refresh(goal)
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
    """Delete goal documentation."""
    goal = get_goal_or_404(db, user, goal_id)
    db.delete(goal)
    db.commit()
