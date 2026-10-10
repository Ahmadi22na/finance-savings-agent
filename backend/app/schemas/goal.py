import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.goal import GoalStatus


class GoalCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150, description="عنوان الهدف")
    icon: str = Field(default="target", description="مفتاح أيقونة يفسّره تطبيق الموبايل (مثل laptop أو plane)")
    target_amount: float = Field(gt=0, description="المبلغ المستهدف بالدينار")
    deadline: date | None = Field(default=None, description="الموعد النهائي (اختياري)")
    # "مصروف ثابت شهري" — نفس الخطة العادية بالضبط، بس بتتصفّر تلقائيًا كل
    # شهر لما توصل لهدفها بدل ما تضل مكتملة للأبد.
    is_recurring: bool = Field(default=False, description="true = مصروف شهري ثابت يُصفَّر تلقائيًا كل شهر بعد اكتماله")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "لابتوب جديد",
                    "icon": "laptop",
                    "target_amount": 600,
                    "deadline": "2027-01-05",
                    "is_recurring": False,
                },
                {"title": "اشتراك النادي", "icon": "dumbbell", "target_amount": 40, "is_recurring": True},
            ]
        }
    }


class GoalContribution(BaseModel):
    """إضافة مبلغ لتقدم الهدف (مثلاً بعد ما المستخدم يوفر مبلغ فعليًا)."""
    amount: float = Field(gt=0, description="المبلغ المضاف بالدينار")

    model_config = {"json_schema_extra": {"examples": [{"amount": 50}]}}


class GoalReorderRequest(BaseModel):
    """
    ترتيب جديد كامل لكل خطط المستخدم النشطة، كلستة IDs بالترتيب المطلوب.
    لازم تحتوي بالضبط نفس مجموعة الخطط النشطة الحالية — كل أو ولا شي،
    عشان نتجنب حالة نص خطط مرتبة ونص لأ.
    """
    ordered_goal_ids: list[uuid.UUID] = Field(
        min_length=1, description="معرّفات الأهداف النشطة بالترتيب المطلوب (الأعلى أولوية أولًا)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ordered_goal_ids": [
                        "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "9c1d2e4a-7b3f-4d58-a1c6-0e5f8b2d7a91",
                    ]
                }
            ]
        }
    }


class GoalOut(BaseModel):
    id: uuid.UUID
    title: str
    icon: str
    target_amount: float
    current_amount: float
    priority: int
    is_recurring: bool
    deadline: date | None
    status: GoalStatus
    progress_percentage: float = Field(description="نسبة التقدم المئوية (0 إلى 100)")
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "title": "لابتوب جديد",
                    "icon": "laptop",
                    "target_amount": 600,
                    "current_amount": 510,
                    "priority": 2,
                    "is_recurring": False,
                    "deadline": "2027-01-05",
                    "status": "active",
                    "progress_percentage": 85.0,
                    "created_at": "2026-08-08T10:47:45Z",
                }
            ]
        },
    }
