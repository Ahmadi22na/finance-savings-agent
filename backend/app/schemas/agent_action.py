import uuid

from pydantic import BaseModel, Field

from app.models.agent import AgentActionType, AgentActionStatus


class AgentActionOut(BaseModel):
    id: uuid.UUID
    action_type: AgentActionType
    status: AgentActionStatus
    payload: dict = Field(
        description=(
            "تفاصيل الاقتراح، وشكلها يعتمد على `action_type`: "
            "`suggest_category_correction` → {transaction_id, new_category_id, new_category_name, "
            "transaction_note, transaction_amount}؛ "
            "`suggest_goal_contribution` → {goal_id, goal_title, amount}؛ "
            "`suggest_goal_creation` → {title, target_amount, breakdown, is_recurring}؛ "
            "`suggest_income_log` → {amount, note}."
        )
    )
    reasoning: str | None = Field(description="سبب الاقتراح بصياغة رشيد (يعرضها التطبيق للمستخدم)")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "action_type": "suggest_goal_contribution",
                    "status": "pending",
                    "payload": {"goal_id": "9c1d2e4a-7b3f-4d58-a1c6-0e5f8b2d7a91", "goal_title": "لابتوب جديد", "amount": 18},
                    "reasoning": "إنت قريب من هدف 'لابتوب جديد' (85%)! دفعة بسيطة بتقرّبك أكتر.",
                }
            ]
        },
    }
