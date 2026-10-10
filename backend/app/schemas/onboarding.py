import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.models.user import IncomeType


class OnboardingComplete(BaseModel):
    """
    يستقبل كل مخرجات شاشات الـ Onboarding الأربع بطلب واحد:
    نوع الدخل، الشخصية المختارة، وأول هدف مالي.
    """
    income_type: IncomeType = Field(description="`fixed` أو `variable`")
    persona_id: uuid.UUID = Field(description="معرّف الشخصية من `GET /personas`")
    goal_title: str = Field(min_length=2, max_length=150, description="عنوان أول هدف")
    goal_target_amount: float = Field(gt=0, description="المبلغ المستهدف لأول هدف (دينار)")
    goal_deadline: date | None = Field(default=None, description="موعد نهائي اختياري")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "income_type": "variable",
                    "persona_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "goal_title": "صندوق الطوارئ",
                    "goal_target_amount": 1000,
                    "goal_deadline": None,
                }
            ]
        }
    }
