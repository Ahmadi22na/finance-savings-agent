from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.docs import UNAUTHORIZED
from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.category import CategoryOut, CategoryCreate
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["Categories"], responses=UNAUTHORIZED)


@router.get(
    "",
    response_model=list[CategoryOut],
    summary="قائمة التصنيفات",
    description=(
        "يرجّع التصنيفات الافتراضية بالإضافة للتصنيفات الخاصة بالمستخدم. `category_type` يحدد "
        "إذا كان التصنيف للمصروف أو الدخل أو كليهما (`both`)."
    ),
)
def list_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return category_service.list_categories_for_user(db, current_user)


@router.post(
    "",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="إنشاء تصنيف خاص",
    description=(
        "ينشئ تصنيفًا خاصًا بالمستخدم بالإضافة للتصنيفات الافتراضية."
    ),
)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return category_service.create_custom_category(db, current_user, data)
