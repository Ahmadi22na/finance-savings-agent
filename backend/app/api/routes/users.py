from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """أول Endpoint محمي بالتطبيق — أي طلب لازم يوصل توكن صالح بالـ Authorization header."""
    return current_user
