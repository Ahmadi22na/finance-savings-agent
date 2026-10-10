from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.docs import conflict, error_response
from app.database.session import get_db
from app.schemas.auth import UserRegister, UserLogin, TokenPair
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    summary="إنشاء حساب جديد",
    description=(
        "ينشئ حسابًا جديدًا ويرجّع زوج التوكنات (`access_token` و`refresh_token`) مع بيانات "
        "المستخدم. رقم الهاتف فريد، وكلمة المرور 8 أحرف على الأقل."
    ),
    responses=conflict("رقم الهاتف مسجّل مسبقًا."),
)
def register(data: UserRegister, db: Session = Depends(get_db)):
    user = auth_service.register_user(db, data)
    return auth_service.build_token_pair(user)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="تسجيل الدخول",
    description=(
        "يتحقق من رقم الهاتف وكلمة المرور ويرجّع زوج التوكنات مع بيانات المستخدم."
    ),
    responses={401: error_response("رقم الهاتف أو كلمة المرور غير صحيحة.")},
)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, data)
    return auth_service.build_token_pair(user)
