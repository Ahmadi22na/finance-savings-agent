import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.agent.mood_engine import MoodState


class PersonaOut(BaseModel):
    """
    ما منرجع system_prompt هون إطلاقًا — هاي تفاصيل داخلية بين رشيد وGemini،
    مو شي المفروض يشوفه المستخدم بشاشة اختيار الشخصية.
    """
    id: uuid.UUID
    key: str
    display_name: str
    tagline: str
    color_hex: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "key": "energetic",
                    "display_name": "رشيد الطاقة",
                    "tagline": "شبابي ومرح وبيحمّسك توفّر",
                    "color_hex": "#F57C00",
                }
            ]
        },
    }


# وسوم جاهزة (بدون نص حر، لتجنب بيانات شخصية): بالترتيب إيجابي ثم ملاحظات
PersonaFeedbackTag = Literal["helpful", "friendly", "motivating", "too_long", "too_pushy", "confusing"]


class PersonaChange(BaseModel):
    """تبديل شخصية رشيد (للتجربة). ما بيغيّر أي بيانات مالية: بس أسلوب حديث رشيد."""
    persona_id: uuid.UUID = Field(description="معرّف الشخصية الجديدة من `GET /personas`")

    model_config = {"json_schema_extra": {"examples": [{"persona_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}]}}


class PersonaFeedbackUpsert(BaseModel):
    persona_id: uuid.UUID = Field(description="الشخصية المُقيَّمة")
    rating: int = Field(ge=1, le=5, description="من 1 (سيئ) إلى 5 (ممتاز)")
    tags: list[PersonaFeedbackTag] = Field(
        default_factory=list,
        max_length=6,
        description="وسوم اختيارية جاهزة: `helpful` `friendly` `motivating` `too_long` `too_pushy` `confusing`",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "persona_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "rating": 4,
                    "tags": ["friendly", "motivating"],
                }
            ]
        }
    }


class PersonaFeedbackOut(BaseModel):
    persona_id: uuid.UUID
    rating: int
    tags: list[str]
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "persona_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "rating": 4,
                    "tags": ["friendly", "motivating"],
                    "updated_at": "2026-10-16T10:00:00Z",
                }
            ]
        },
    }


class MoodStateOut(BaseModel):
    state: MoodState
    reason: str
