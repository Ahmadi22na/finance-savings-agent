"""Module documentation."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin


def register_user(db: Session, data: UserRegister) -> User:
    existing = db.query(User).filter(User.phone == data.phone).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="رقم الهاتف مسجّل مسبقًا")

    user = User(
        name=data.name,
        phone=data.phone,
        hashed_password=hash_password(data.password),
        income_type=data.income_type,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, data: UserLogin) -> User:
    user = db.query(User).filter(User.phone == data.phone).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="رقم الهاتف أو كلمة المرور غير صحيحة")
    return user


def build_token_pair(user: User) -> dict:
    subject = str(user.id)
    return {
        "access_token": create_access_token(subject),
        "refresh_token": create_refresh_token(subject),
        "token_type": "bearer",
        "user": user,
    }
