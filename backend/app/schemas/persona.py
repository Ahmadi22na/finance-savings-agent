import uuid

from pydantic import BaseModel

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


class MoodStateOut(BaseModel):
    state: MoodState
    reason: str
