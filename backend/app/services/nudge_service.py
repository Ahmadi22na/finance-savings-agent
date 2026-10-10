"""
Nudge Service — رشيد يبادر بالحديث، مو بس يرد.

قرارين تصميم مهمين هون:
1. ما نبعث Nudge إلا لو الحالة المزاجية energized أو concerned — الحالة neutral
   مالها داعي نزعج فيها المستخدم، رشيد ساكت لحد ما يصير في شي يستاهل يحكي فيه.
2. Cooldown صارم (12 ساعة افتراضيًا) بغض النظر عن الحالة — حتى لو المستخدم
   "concerned" باستمرار، ما نقصفه برسائل متكررة. هذا يحمي من نمط مزعج
   (بالضبط عكس يلي طلبته من أول محادثة: "بنّاء وما بييأس" مش "يلاحق ويكرر").
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.log_safety import safe_error
from app.agent.mood_engine import compute_mood_state, build_full_system_prompt, MoodState
from app.agent.providers.factory import get_ai_provider
from app.models.agent import AgentInteraction, InteractionTrigger
from app.models.user import User

logger = logging.getLogger("rasheed.agent")

NUDGE_COOLDOWN_HOURS = 12

# التعليمة يلي منرسلها لرشيد عشان "يبادر" بدل ما يرد على رسالة مستخدم
NUDGE_INSTRUCTION = (
    "بادر إنت بالحديث الآن — المستخدم ما كتب إلك شي، إنت يلي بلّشت. "
    "اكتب رسالة قصيرة (سطر أو سطرين بالكثير) تناسب حالتك المزاجية الحالية تجاهه، "
    "بأسلوب شخصيتك المحدد. ما تسأله \"شو صاير\" أو \"كيفك\" بشكل عام — خاطبه مباشرة "
    "وبشكل محدد بناءً على السبب المذكور بحالتك المزاجية."
)


def _get_last_nudge_time(db: Session, user: User) -> datetime | None:
    last_nudge = (
        db.query(AgentInteraction)
        .filter(
            AgentInteraction.user_id == user.id,
            AgentInteraction.trigger_type == InteractionTrigger.NUDGE,
            AgentInteraction.is_from_user.is_(False),
        )
        .order_by(AgentInteraction.created_at.desc())
        .first()
    )
    return last_nudge.created_at if last_nudge else None


def check_and_generate_nudge(db: Session, user: User) -> str | None:
    """يرجّع نص الـ Nudge لو يستاهل يُرسل هلأ، أو None لو ما في داعي (منطقي ومقصود، مش خطأ)."""
    if user.persona is None:
        return None  # ما خلص Onboarding لسا، ما إله شخصية تحكي أصلاً

    mood = compute_mood_state(db, user)
    if mood.state == MoodState.NEUTRAL:
        return None

    last_nudge_at = _get_last_nudge_time(db, user)
    if last_nudge_at is not None:
        # SQLite (المستخدم بالاختبارات) ما بيحافظ على معلومة الـ timezone عند القراءة —
        # لو رجع تاريخ "ساذج" (naive)، نفترضه UTC بما إنه هيك خزّناه أصلاً
        if last_nudge_at.tzinfo is None:
            last_nudge_at = last_nudge_at.replace(tzinfo=timezone.utc)
        cooldown_ends = last_nudge_at + timedelta(hours=NUDGE_COOLDOWN_HOURS)
        if datetime.now(timezone.utc) < cooldown_ends:
            return None  # لسا بفترة الراحة — ما نزعج المستخدم

    full_system_prompt = build_full_system_prompt(user, mood.state.value, mood.reason)

    provider = get_ai_provider()
    reply = provider.generate_reply(full_system_prompt, NUDGE_INSTRUCTION)

    if reply.raw_error:
        logger.error("Gemini provider error while generating nudge for user %s: %s", user.id, safe_error(reply.raw_error))
        return None  # ما نبعث Nudge فاشل أو فاضي للمستخدم — بس نسجل ونسكت هالمرة

    db.add(AgentInteraction(
        user_id=user.id, trigger_type=InteractionTrigger.NUDGE,
        message=reply.text, is_from_user=False,
    ))
    db.commit()

    return reply.text
