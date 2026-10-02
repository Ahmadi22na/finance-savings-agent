from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.models.user import User
from app.schemas.onboarding import OnboardingComplete
from app.services import persona_service


def complete_onboarding(db: Session, user: User, data: OnboardingComplete) -> User:
    if user.has_completed_onboarding:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="المستخدم خلّص الـ Onboarding مسبقًا",
        )


    persona = persona_service.get_persona_or_404(db, data.persona_id)

    user.income_type = data.income_type
    user.persona_id = persona.id
    user.has_completed_onboarding = True

    first_goal = Goal(
        user_id=user.id,
        title=data.goal_title,
        target_amount=data.goal_target_amount,
        deadline=data.goal_deadline,
    )
    db.add(first_goal)
    db.commit()
    db.refresh(user)
    return user
