import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.persona import Persona
from app.models.persona_feedback import PersonaFeedback
from app.models.user import User


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


def change_persona(db: Session, user: User, persona_id) -> User:
    """تبديل الشخصية للتجربة. بيغيّر persona_id فقط؛ الأهداف والمعاملات والمزاج ما بتتأثر (مستقلة عن الشخصية)."""
    persona = get_persona_or_404(db, persona_id)  # لازم موجودة ومفعّلة
    user.persona_id = persona.id
    db.commit()
    db.refresh(user)
    return user


def upsert_feedback(db: Session, user: User, persona_id, rating: int, tags: list[str]) -> PersonaFeedback:
    """تقييم واحد لكل (مستخدم، شخصية): إعادة التقييم بتحدّث نفس السطر. الشخصية لازم تكون موجودة (حتى لو موقوفة)."""
    persona = db.get(Persona, persona_id)
    if persona is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الشخصية غير موجودة")

    unique_tags = sorted(set(tags))
    feedback = (
        db.query(PersonaFeedback)
        .filter(PersonaFeedback.user_id == user.id, PersonaFeedback.persona_id == persona.id)
        .first()
    )
    if feedback is None:
        feedback = PersonaFeedback(user_id=user.id, persona_id=persona.id, rating=rating, tags=unique_tags)
        db.add(feedback)
    else:
        feedback.rating = rating
        feedback.tags = unique_tags
    db.commit()
    db.refresh(feedback)
    return feedback


def list_feedback_for_user(db: Session, user: User) -> list[PersonaFeedback]:
    return (
        db.query(PersonaFeedback)
        .filter(PersonaFeedback.user_id == user.id)
        .order_by(PersonaFeedback.updated_at.desc())
        .all()
    )
