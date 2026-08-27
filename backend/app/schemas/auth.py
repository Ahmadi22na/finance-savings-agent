import uuid

from pydantic import BaseModel, Field

from app.models.user import IncomeType
from app.schemas.persona import PersonaOut


class UserRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=8, description="8 أحرف على الأقل")
    income_type: IncomeType = IncomeType.VARIABLE


class UserLogin(BaseModel):
    phone: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    income_type: IncomeType
    agent_name: str
    has_completed_onboarding: bool
    persona: PersonaOut | None = None

    model_config = {"from_attributes": True}


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
