import uuid

from pydantic import BaseModel

from app.agent.mood_engine import MoodState


class PersonaOut(BaseModel):
    """Personaout documentation."""
    id: uuid.UUID
    key: str
    display_name: str
    tagline: str
    color_hex: str

    model_config = {"from_attributes": True}


class MoodStateOut(BaseModel):
    state: MoodState
    reason: str
