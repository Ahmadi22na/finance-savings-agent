"""
Dependencies مشتركة لـ FastAPI — بشكل رئيسي: التحقق من هوية المستخدم عبر الـ JWT.
"""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database.session import get_db
from app.models.user import User

# auto_error=False عشان نرجّع 401 بنفسنا بكل إصدارات FastAPI: الإصدارات القديمة (مثل 0.115) كانت ترجّع 403
# لما التوكن مفقود، والجديدة 401. هيك السلوك ثابت ومطابق للتوثيق وللمعيار (401 + WWW-Authenticate).
bearer_scheme = HTTPBearer(auto_error=False)

UNAUTHENTICATED_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="لازم تسجّل الدخول (التوكن مفقود)",
            headers=UNAUTHENTICATED_HEADERS,
        )

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="توكن غير صالح أو منتهي الصلاحية",
            headers=UNAUTHENTICATED_HEADERS,
        )

    user_id = payload.get("sub")
    try:
        user = db.get(User, uuid.UUID(user_id))
    except (ValueError, TypeError):
        user = None

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="المستخدم غير موجود أو غير مفعّل",
            headers=UNAUTHENTICATED_HEADERS,
        )

    return user
