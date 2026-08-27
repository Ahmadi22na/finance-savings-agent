import enum
import uuid

from sqlalchemy import String, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class IncomeType(str, enum.Enum):
    """
    نوع الدخل: مهم جدًا لرشيد ليفهم السياق قبل ما ينبّه المستخدم.
    مستخدم دخله متغير ما لازم يُقارن بنفس معايير مستخدم دخله ثابت.
    """
    FIXED = "fixed"
    VARIABLE = "variable"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- سياق الدخل (لفهم رشيد للمستخدم) ---
    income_type: Mapped[IncomeType] = mapped_column(
        SAEnum(IncomeType, name="income_type_enum"), default=IncomeType.VARIABLE
    )
    avg_monthly_income_estimate: Mapped[float | None] = mapped_column(nullable=True)

    # --- تخصيص الوكيل ---
    agent_name: Mapped[str] = mapped_column(String(50), default="رشيد")
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True
    )
    has_completed_onboarding: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- العلاقات ---
    persona: Mapped["Persona | None"] = relationship(back_populates="users")
    goals: Mapped[list["Goal"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    agent_interactions: Mapped[list["AgentInteraction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    agent_actions: Mapped[list["AgentAction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
