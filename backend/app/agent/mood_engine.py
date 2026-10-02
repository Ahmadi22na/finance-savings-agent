"""Module documentation."""
import enum
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.goal import Goal, GoalStatus
from app.models.transaction import Transaction, TransactionType
from app.models.user import User


def build_full_system_prompt(user: User, mood_state: str, mood_reason: str) -> str:
    """Build full system prompt documentation."""
    return (
        f"{user.persona.system_prompt}\n\n"
        f"معلومات إضافية عن المستخدم الحالي (استخدمها بذكاء، ما تكررها حرفيًا):\n"
        f"- اسمه: {user.name}\n"
        f"- حالتك المزاجية الحالية تجاهه: {mood_state} — السبب: {mood_reason}"
    )


RECENT_WINDOW_DAYS = 7
BASELINE_WINDOW_DAYS = 30


OVERSPENDING_THRESHOLD_RATIO = 1.5


GOAL_PROGRESS_BOOST_THRESHOLD = 0.05


class MoodState(str, enum.Enum):
    NEUTRAL = "neutral"
    ENERGIZED = "energized"
    CONCERNED = "concerned"


@dataclass
class MoodResult:
    state: MoodState
    reason: str


def compute_mood_state(db: Session, user: User) -> MoodResult:
    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(days=RECENT_WINDOW_DAYS)
    baseline_start = now - timedelta(days=BASELINE_WINDOW_DAYS)

    recent_expenses = _sum_expenses(db, user, recent_start, now)
    baseline_expenses = _sum_expenses(db, user, baseline_start, recent_start)


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
