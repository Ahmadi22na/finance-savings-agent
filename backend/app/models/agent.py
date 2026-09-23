import enum

from sqlalchemy import String, Text, Enum as SAEnum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class InteractionTrigger(str, enum.Enum):
    NUDGE = "nudge"
    MONTHLY_INSIGHT = "monthly_insight"
    USER_CHAT = "user_chat"
    GOAL_MILESTONE = "goal_milestone"


class AgentInteraction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_interactions"

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    trigger_type: Mapped[InteractionTrigger] = mapped_column(
        SAEnum(InteractionTrigger, name="interaction_trigger_enum")
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_from_user: Mapped[bool] = mapped_column(default=False)

    user: Mapped["User"] = relationship(back_populates="agent_interactions")


class AgentActionType(str, enum.Enum):
    SUGGEST_CATEGORY_CORRECTION = "suggest_category_correction"
    SUGGEST_BUDGET_ADJUSTMENT = "suggest_budget_adjustment"
    SUGGEST_GOAL_CONTRIBUTION = "suggest_goal_contribution"
    SUGGEST_GOAL_CREATION = "suggest_goal_creation"
    # جديد: رشيد يقترح تسجيل دخل ذكره المستخدم بالمحادثة الحرة (مثال:
    # "اشتغلت يوم واجاني 25 دينار") — بدل ما تضيع المعلومة أو تُفهم غلط
    # كوصف هدف جديد.
    SUGGEST_INCOME_LOG = "suggest_income_log"


class AgentActionStatus(str, enum.Enum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"


class AgentAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_actions"

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    action_type: Mapped[AgentActionType] = mapped_column(SAEnum(AgentActionType, name="agent_action_type_enum"))
    status: Mapped[AgentActionStatus] = mapped_column(
        SAEnum(AgentActionStatus, name="agent_action_status_enum"), default=AgentActionStatus.PENDING
    )

    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="agent_actions")
