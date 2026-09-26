import enum
from datetime import date

from sqlalchemy import String, Numeric, Date, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"


class Goal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "goals"

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String(150), nullable=False)  # مثال: "رحلة سفر" أو "مشروع خاص"
    icon: Mapped[str] = mapped_column(String(50), default="target")

    # Numeric بدل Float للمبالغ المالية دايمًا — Float فيه أخطاء تقريب خطيرة بالحسابات المالية
    target_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    current_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # ترتيب الأولوية بين خطط نفس المستخدم — رقم أصغر = أولوية أعلى.
    # ما بنستخدم created_at للترتيب لأنه المستخدم لازم يقدر يعيد الترتيب يدويًا
    # (سحب وإفلات بالموبايل) بدون ما نغيّر تاريخ الإنشاء الحقيقي.
    priority: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)

    # "مصروف ثابت شهري" (زي إيجار، اشتراك) هو نفس جدول الخطط بالضبط — الفرق
    # الوحيد هو هالعلم. لما يكتمل (current_amount >= target_amount)، بدل ما
    # يضل ACHIEVED للأبد، بيرجع يتصفّر تلقائيًا أول ما يبلش شهر جديد.
    is_recurring: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    # آخر شهر (بصيغة "YYYY-MM") انفحصت/انصفّرت فيه هاي الخطة — تستخدم بس
    # لخطط is_recurring، لتطبيق Lazy Reset بدون الحاجة لمهمة خلفية دايمة
    # الاشتغال (Cron). None يعني لسا ما انفحصت أو مش recurring أصلاً.
    last_reset_month: Mapped[str | None] = mapped_column(String(7), nullable=True)

    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[GoalStatus] = mapped_column(
        SAEnum(GoalStatus, name="goal_status_enum"), default=GoalStatus.ACTIVE
    )

    user: Mapped["User"] = relationship(back_populates="goals")

    @property
    def progress_percentage(self) -> float:
        """نسبة تحقيق الهدف — يستخدمها رشيد كثيرًا بالتشجيع والتنبيهات."""
        if self.target_amount <= 0:
            return 0.0
        return round(min(float(self.current_amount) / float(self.target_amount), 1.0) * 100, 1)
