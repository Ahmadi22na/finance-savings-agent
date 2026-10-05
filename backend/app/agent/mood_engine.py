"""
Mood Engine.

هذا المحرك بيحدد "حالة" رشيد (بغض النظر عن الشخصية المختارة): طبيعي، متحمس، أو قلقان.
الموبايل بيستخدم هالحالة ليعرض الرسمة المناسبة (كل شخصية إلها رسمة لكل حالة)،
ورشيد بيستخدمها كسياق إضافي بالـ System Prompt لما يحكي مع المستخدم أو يبعثله Nudge.

قرار تصميم: هالمنطق Rule-based بسيط اليوم (متل الـ Categorizer بالضبط) —
قابل للتطوير لاحقًا لمنطق أعقد (تحليل اتجاهات، توقعات) بدون ما نغيّر شكل الواجهة
يلي بستخدمها الموبايل والـ Agent.
"""
import enum
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.goal import Goal, GoalStatus
from app.models.transaction import Transaction, TransactionType
from app.models.user import User


def build_full_system_prompt(user: User, mood_state: str, mood_reason: str) -> str:
    """
    يجمع System Prompt الشخصية المختارة + سياق المستخدم + حالته المزاجية الحالية
    بشكل موحّد — يُستخدم من agent_chat_service و nudge_service معًا، عشان أي
    تعديل مستقبلي على شكل الـ Prompt (مثلاً إضافة بيانات هدف المستخدم) يصير
    بمكان واحد بس.
    """
    return (
        f"{user.persona.system_prompt}\n\n"
        f"معلومات إضافية عن المستخدم الحالي (استخدمها بذكاء، ما تكررها حرفيًا):\n"
        f"- اسمه: {user.name}\n"
        f"- حالتك المزاجية الحالية تجاهه: {mood_state} — السبب: {mood_reason}"
    )


# النافذة الزمنية يلي منقارن فيها "الفترة الأخيرة" بمعدل إنفاق المستخدم المعتاد
RECENT_WINDOW_DAYS = 7
BASELINE_WINDOW_DAYS = 30

# لو صرف الأسبوع الأخير أعلى من المعدل المعتاد بهاي النسبة، هاي إشارة "قلقان"
OVERSPENDING_THRESHOLD_RATIO = 1.5

# لو أي هدف نشط تقدمه زاد بهاي النسبة أو أكتر خلال الفترة الأخيرة، هاي إشارة "متحمس"
GOAL_PROGRESS_BOOST_THRESHOLD = 0.05  # 5% تقدم إضافي


class MoodState(str, enum.Enum):
    NEUTRAL = "neutral"        # الحالة الافتراضية — ولا إشارة قوية بأي اتجاه
    ENERGIZED = "energized"    # قريب من هدفه / منضبط بمصروفه مؤخرًا
    CONCERNED = "concerned"    # صرف زيادة عن المعتاد أو ابتعد عن هدفه


@dataclass
class MoodResult:
    state: MoodState
    reason: str  # شرح مختصر (يُستخدم بالـ System Prompt عشان رشيد يفهم ليش هاي حالته)


def compute_mood_state(db: Session, user: User) -> MoodResult:
    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(days=RECENT_WINDOW_DAYS)
    baseline_start = now - timedelta(days=BASELINE_WINDOW_DAYS)

    recent_expenses = _sum_expenses(db, user, recent_start, now)
    baseline_expenses = _sum_expenses(db, user, baseline_start, recent_start)

    # نطبّع معدل الـ baseline (23 يوم) لنفس طول نافذة الأسبوع عشان المقارنة تكون عادلة
    baseline_days = max((recent_start - baseline_start).days, 1)
    normalized_baseline = (baseline_expenses / baseline_days) * RECENT_WINDOW_DAYS

    if normalized_baseline > 0 and recent_expenses > normalized_baseline * OVERSPENDING_THRESHOLD_RATIO:
        return MoodResult(
            state=MoodState.CONCERNED,
            reason=f"صرف الأسبوع الأخير ({recent_expenses:.0f}) أعلى بوضوح من معدله المعتاد",
        )

    active_goal = (
        db.query(Goal)
        .filter(Goal.user_id == user.id, Goal.status == GoalStatus.ACTIVE)
        .order_by(Goal.created_at.desc())
        .first()
    )
    if active_goal and float(active_goal.target_amount) > 0:
        progress_ratio = float(active_goal.current_amount) / float(active_goal.target_amount)
        if progress_ratio >= 0.8:
            return MoodResult(
                state=MoodState.ENERGIZED,
                reason=f"قريب جدًا من هدف '{active_goal.title}' ({active_goal.progress_percentage}%)",
            )

    return MoodResult(state=MoodState.NEUTRAL, reason="ولا إشارة قوية — كل شي طبيعي")


def _sum_expenses(db: Session, user: User, start: datetime, end: datetime) -> float:
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.occurred_at >= start,
            Transaction.occurred_at < end,
        )
        .all()
    )
    return sum(float(t.amount) for t in transactions)
