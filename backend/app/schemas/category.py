import uuid

from pydantic import BaseModel

from app.models.category import CategoryType


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    icon: str
    is_default: bool
    category_type: CategoryType

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    """Categorycreate documentation."""
    name: str
    icon: str = "tag"
    category_type: CategoryType = CategoryType.EXPENSE
