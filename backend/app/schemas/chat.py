from pydantic import BaseModel, Field


class ChatMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=1000, description="نص رسالة المستخدم لرشيد")

    model_config = {"json_schema_extra": {"examples": [{"message": "كم باقيلي عشان أوصل لهدفي؟"}]}}


class ChatMessageOut(BaseModel):
    reply: str = Field(description="رد رشيد (نص عادي، بدون أي وسوم داخلية)")
    ai_available: bool = Field(
        default=True,
        description=(
            "false = تعذّر الوصول لخدمة الذكاء الاصطناعي: `reply` رسالة اعتذار، ولم تُحفظ الرسالة "
            "بسجل المحادثة، فإعادة إرسالها آمنة."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"reply": "باقيلك 90 دينار على اللابتوب، كمل بنفس الوتيرة!", "ai_available": True}]
        }
    }


class NudgeOut(BaseModel):
    # None يعني "ولا داعي لأي رسالة هلأ" — حالة طبيعية ومقصودة
    nudge: str | None = Field(description="رسالة رشيد المبادِرة، أو null إذا لا داعي لأي رسالة الآن")

    model_config = {"json_schema_extra": {"examples": [{"nudge": "ما شاء الله، صرت قريب من هدفك!"}, {"nudge": None}]}}
