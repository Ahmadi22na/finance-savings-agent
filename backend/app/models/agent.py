import enum

from sqlalchemy import String, Text, Enum as SAEnum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class InteractionTrigger(str, enum.Enum):
    """كيف بلش هذا التفاعل — يفرّق بين رسالة رشيد الاستباقية ورد فعله على المستخدم."""
    NUDGE = "nudge"              # تنبيه استباقي مرح (مثال: موضوع الحلاقة)
    MONTHLY_INSIGHT = "monthly_insight"  # ملخص شهري عند الدخول للتطبيق
    USER_CHAT = "user_chat"      # المستخدم بلش المحادثة
    GOAL_MILESTONE = "goal_milestone"    # وصول لنسبة معينة من الهدف


class AgentInteraction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    سجل كل تفاعل من رشيد. هذا الجدول أساسي لسببين:
    1. تحسين شخصية رشيد بمرور الوقت بناءً على استجابة المستخدم.
    2. Engagement Metrics — أهم دليل لعرضه على شركة المحفظة لاحقًا.
    """
    __tablename__ = "agent_interactions"

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    trigger_type: Mapped[InteractionTrigger] = mapped_column(
        SAEnum(InteractionTrigger, name="interaction_trigger_enum")
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_from_user: Mapped[bool] = mapped_column(default=False)  # False = رشيد هو يلي حكى

    user: Mapped["User"] = relationship(back_populates="agent_interactions")


class AgentActionType(str, enum.Enum):
    SUGGEST_CATEGORY_CORRECTION = "suggest_category_correction"
    SUGGEST_BUDGET_ADJUSTMENT = "suggest_budget_adjustment"
    SUGGEST_GOAL_CONTRIBUTION = "suggest_goal_contribution"


class AgentActionStatus(str, enum.Enum):
    PENDING = "pending"    # رشيد اقترح، بانتظار موافقة المستخدم
    APPLIED = "applied"    # المستخدم وافق وتم التنفيذ فعليًا على قاعدة البيانات
    REJECTED = "rejected"  # المستخدم رفض الاقتراح


class AgentAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    هذا الجدول هو يلي بيخلي رشيد 'يطبّق' مش بس 'يحكي'.
    أي اقتراح لرشيد بالتعديل على بيانات المستخدم يتسجل هون أولاً بحالة PENDING،
    وما بينفذ فعليًا إلا بعد موافقة صريحة من المستخدم — هذا مبدأ أمان أساسي
    لأي Agent إله صلاحية التعديل على بيانات مالية.
    """
    __tablename__ = "agent_actions"

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    action_type: Mapped[AgentActionType] = mapped_column(SAEnum(AgentActionType, name="agent_action_type_enum"))
    status: Mapped[AgentActionStatus] = mapped_column(
        SAEnum(AgentActionStatus, name="agent_action_status_enum"), default=AgentActionStatus.PENDING
    )

    # تفاصيل الاقتراح بشكل مرن (مثلاً: {"transaction_id": "...", "old_category": "...", "new_category": "..."})
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)  # شرح رشيد لسبب اقتراحه

    user: Mapped["User"] = relationship(back_populates="agent_actions")
