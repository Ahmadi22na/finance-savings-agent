import uuid
from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.models.user import IncomeType


class OnboardingComplete(BaseModel):
    """
    مخرجات الـ Onboarding بطلب واحد. **كل الحقول اختيارية** عشان المستخدم يوصل للتطبيق بأسرع وقت:
    - بدون `persona_id` بنختار الشخصية الافتراضية.
    - بدون `income_type` بنفترض `variable` (جمهورنا: دخل غير منتظم).
    - الهدف الأول اختياري، بس لو انبعت لازم ينبعت `goal_title` و`goal_target_amount` مع بعض.
    """
    income_type: IncomeType = Field(
        default=IncomeType.VARIABLE, description="`fixed` أو `variable` (الافتراضي `variable`)"
    )
    persona_id: uuid.UUID | None = Field(
        default=None, description="معرّف الشخصية من `GET /personas`؛ لو ما انبعت بتنختار الشخصية الافتراضية"
    )
    goal_title: str | None = Field(default=None, min_length=2, max_length=150, description="عنوان أول هدف (اختياري)")
    goal_target_amount: float | None = Field(
        default=None, gt=0, description="المبلغ المستهدف لأول هدف بالدينار (مع `goal_title` أو بدونهم كلاهما)"
    )
    goal_deadline: date | None = Field(default=None, description="موعد نهائي اختياري (يحتاج هدف)")

    @model_validator(mode="after")
    def goal_fields_come_together(self):
        if (self.goal_title is None) != (self.goal_target_amount is None):
            raise ValueError("اسم الهدف والمبلغ المستهدف لازم ينبعتوا مع بعض، أو ولا واحد منهم")
        if self.goal_deadline is not None and self.goal_title is None:
            raise ValueError("الموعد النهائي بحاجة لهدف")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "income_type": "variable",
                    "persona_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "goal_title": "صندوق الطوارئ",
                    "goal_target_amount": 1000,
                    "goal_deadline": None,
                },
                {},
            ]
        }
    }
