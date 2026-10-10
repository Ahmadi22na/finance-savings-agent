import uuid

from pydantic import BaseModel, Field

from app.models.category import CategoryType


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    icon: str
    is_default: bool = Field(description="true = تصنيف افتراضي من النظام، false = أنشأه المستخدم")
    category_type: CategoryType

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "name": "مطاعم وكافيهات",
                    "icon": "restaurant",
                    "is_default": True,
                    "category_type": "expense",
                }
            ]
        },
    }


class CategoryCreate(BaseModel):
    """تصنيف خاص ينشئه المستخدم بنفسه (بالإضافة للتصنيفات الافتراضية)."""
    name: str = Field(description="اسم التصنيف")
    icon: str = Field(default="tag", description="مفتاح أيقونة يفسّره تطبيق الموبايل")
    category_type: CategoryType = Field(default=CategoryType.EXPENSE, description="`expense` أو `income` أو `both`")

    model_config = {"json_schema_extra": {"examples": [{"name": "هدايا", "icon": "gift", "category_type": "expense"}]}}
