import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.goal import GoalStatus


class GoalCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    icon: str = "target"
    target_amount: float = Field(gt=0)
    deadline: date | None = None


    is_recurring: bool = False


class GoalContribution(BaseModel):
    """Goalcontribution documentation."""
    amount: float = Field(gt=0)


class GoalReorderRequest(BaseModel):
    """Goalreorderrequest documentation."""
    ordered_goal_ids: list[uuid.UUID] = Field(min_length=1)


class GoalOut(BaseModel):
    id: uuid.UUID
    title: str
    icon: str
    target_amount: float
    current_amount: float
    priority: int
    is_recurring: bool
    deadline: date | None
    status: GoalStatus
    progress_percentage: float
    created_at: datetime

    model_config = {"from_attributes": True}
