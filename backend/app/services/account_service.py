"""
حذف الحساب وكل البيانات المرتبطة به (R04).

بنحذف بشكل صريح (bulk delete) بدل ما نعتمد على الـ cascade لحاله: هيك السلوك نفسه على Postgres وSQLite،
وما بيبقى أي سجل يتيم لو cascade معيّن غلط أو ناقص بجدول جديد. كل شي بمعاملة وحدة (كله أو ولا شي).
"""
import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.agent import AgentAction, AgentInteraction
from app.models.active_day import UserActiveDay
from app.models.ai_usage import AiUsageEvent
from app.models.category import Category
from app.models.goal import Goal
from app.models.goal_movement import GoalMovement
from app.models.income_allocation import IncomeAllocation
from app.models.persona_feedback import PersonaFeedback
from app.models.transaction import Transaction
from app.models.user import User

logger = logging.getLogger("rasheed.account")


def delete_account(db: Session, user: User, password: str) -> None:
    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="كلمة المرور غير صحيحة")

    user_id = user.id
    user_transactions = select(Transaction.id).where(Transaction.user_id == user_id)
    user_goals = select(Goal.id).where(Goal.user_id == user_id)

    try:
        # الترتيب مهم: الجداول الي بتشير لغيرها أول
        db.query(IncomeAllocation).filter(IncomeAllocation.transaction_id.in_(user_transactions)).delete(
            synchronize_session=False
        )
        db.query(IncomeAllocation).filter(IncomeAllocation.goal_id.in_(user_goals)).delete(synchronize_session=False)
        db.query(GoalMovement).filter(GoalMovement.goal_id.in_(user_goals)).delete(synchronize_session=False)
        db.query(AgentAction).filter(AgentAction.user_id == user_id).delete(synchronize_session=False)
        db.query(AgentInteraction).filter(AgentInteraction.user_id == user_id).delete(synchronize_session=False)
        db.query(AiUsageEvent).filter(AiUsageEvent.user_id == user_id).delete(synchronize_session=False)
        db.query(UserActiveDay).filter(UserActiveDay.user_id == user_id).delete(synchronize_session=False)
        db.query(PersonaFeedback).filter(PersonaFeedback.user_id == user_id).delete(synchronize_session=False)
        db.query(Transaction).filter(Transaction.user_id == user_id).delete(synchronize_session=False)
        db.query(Goal).filter(Goal.user_id == user_id).delete(synchronize_session=False)
        db.query(Category).filter(Category.user_id == user_id).delete(synchronize_session=False)  # التصنيفات الخاصة فقط
        db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Account deletion failed for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ما قدرنا نحذف الحساب هلأ، ما انحذف شي. جرب كمان شوي",
        )

    db.expire_all()
    logger.info("Account deleted: user=%s", user_id)
