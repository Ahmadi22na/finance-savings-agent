import uuid

from pydantic import BaseModel, Field

from app.models.user import IncomeType
from app.schemas.persona import PersonaOut


class UserRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100, description="الاسم الظاهر للمستخدم")
    phone: str = Field(min_length=8, max_length=20, description="رقم الهاتف — فريد لكل حساب")
    password: str = Field(min_length=8, description="8 أحرف على الأقل")
    income_type: IncomeType = Field(
        default=IncomeType.VARIABLE,
        description="`fixed` دخل ثابت (راتب)، أو `variable` دخل غير منتظم (فريلانس/أجرة يومية)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "سامر", "phone": "0791234567", "password": "Passw0rd!", "income_type": "variable"}
            ]
        }
    }


class UserLogin(BaseModel):
    phone: str = Field(description="رقم الهاتف المسجَّل")
    password: str = Field(description="كلمة المرور")

    model_config = {"json_schema_extra": {"examples": [{"phone": "0791234567", "password": "Passw0rd!"}]}}


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    income_type: IncomeType
    agent_name: str
    has_completed_onboarding: bool
    persona: PersonaOut | None = Field(default=None, description="الشخصية المختارة (null قبل إتمام الـ Onboarding)")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "9c1d2e4a-7b3f-4d58-a1c6-0e5f8b2d7a91",
                    "name": "سامر",
                    "phone": "0791234567",
                    "income_type": "variable",
                    "agent_name": "رشيد",
                    "has_completed_onboarding": True,
                    "persona": {
                        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "key": "energetic",
                        "display_name": "رشيد الطاقة",
                        "tagline": "شبابي ومرح وبيحمّسك توفّر",
                        "color_hex": "#F57C00",
                    },
                }
            ]
        },
    }


class TokenPair(BaseModel):
    access_token: str = Field(description="يُرسل بالهيدر: Authorization: Bearer <access_token>")
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
