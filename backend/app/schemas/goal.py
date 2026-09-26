import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.goal import GoalStatus


class GoalCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    icon: str = "target"
    target_amount: float = Field(gt=0)
    deadline: date | None = None


class GoalContribution(BaseModel):
    """إضافة مبلغ لتقدم الهدف (مثلاً بعد ما المستخدم يوفر مبلغ فعليًا)."""
    amount: float = Field(gt=0)


class GoalReorderRequest(BaseModel):
    """
    ترتيب جديد كامل لكل خطط المستخدم النشطة، كلستة IDs بالترتيب المطلوب.
    لازم تحتوي بالضبط نفس مجموعة الخطط النشطة الحالية — كل أو ولا شي،
    عشان نتجنب حالة نص خطط مرتبة ونص لأ.
    """
    ordered_goal_ids: list[uuid.UUID] = Field(min_length=1)


class GoalOut(BaseModel):
    id: uuid.UUID
    title: str
    icon: str
    target_amount: float
    current_amount: float
    priority: int
    deadline: date | None
    status: GoalStatus
    progress_percentage: float
    created_at: datetime

    model_config = {"from_attributes": True}
