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

    model_config = {"from_attributes": True}


class MoodStateOut(BaseModel):
    state: MoodState
    reason: str
