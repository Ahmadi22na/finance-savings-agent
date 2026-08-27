from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.persona import PersonaOut
from app.services import persona_service

router = APIRouter(prefix="/personas", tags=["Personas"])


@router.get("", response_model=list[PersonaOut])
def list_personas(db: Session = Depends(get_db)):
    """
    ما محتاج توثيق (Auth) — هاي الشاشة تظهر أثناء الـ Onboarding قبل ما نعرف هوية المستخدم الكاملة.
    """
    return persona_service.list_active_personas(db)
