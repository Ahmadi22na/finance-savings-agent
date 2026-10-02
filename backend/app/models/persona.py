"""Module documentation."""
from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class Persona(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "personas"

    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tagline: Mapped[str] = mapped_column(String(200), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)          # "#1B4332"



    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users: Mapped[list["User"]] = relationship(back_populates="persona")
