import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.models.user import IncomeType


class OnboardingComplete(BaseModel):
    """Onboardingcomplete documentation."""
    income_type: IncomeType
    persona_id: uuid.UUID
    goal_title: str = Field(min_length=2, max_length=150)
    goal_target_amount: float = Field(gt=0)
    goal_deadline: date | None = None
