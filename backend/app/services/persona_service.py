import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.persona import Persona


def list_active_personas(db: Session) -> list[Persona]:
    return db.query(Persona).filter(Persona.is_active.is_(True)).order_by(Persona.created_at).all()


def get_default_persona(db: Session) -> Persona | None:
    """الشخصية الافتراضية (DEFAULT_PERSONA_KEY)، وإذا مش موجودة أو مش مفعّلة، أول شخصية مفعّلة."""
    preferred = db.query(Persona).filter(Persona.key == settings.DEFAULT_PERSONA_KEY, Persona.is_active.is_(True)).first()
    if preferred is not None:
        return preferred
    active = list_active_personas(db)
    return active[0] if active else None


def get_persona_or_404(db: Session, persona_id: uuid.UUID) -> Persona:
    persona = db.query(Persona).filter(Persona.id == persona_id, Persona.is_active.is_(True)).first()
    if persona is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الشخصية غير موجودة")
    return persona
