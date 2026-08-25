from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.user import User
from app.schemas.category import CategoryCreate


def list_categories_for_user(db: Session, user: User) -> list[Category]:
    """التصنيفات الافتراضية (متاحة للجميع) + التصنيفات الخاصة يلي أنشأها هذا المستخدم بالذات."""
    return (
        db.query(Category)
        .filter(or_(Category.is_default.is_(True), Category.user_id == user.id))
        .order_by(Category.is_default.desc(), Category.name)
        .all()
    )


def create_custom_category(db: Session, user: User, data: CategoryCreate) -> Category:
    category = Category(
        name=data.name,
        icon=data.icon,
        category_type=data.category_type,
        is_default=False,
        user_id=user.id,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category
