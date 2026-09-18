import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agent.mood_engine import compute_mood_state, build_full_system_prompt
from app.agent.providers.base import ConversationTurn
from app.agent.providers.factory import get_ai_provider
from app.models.agent import AgentInteraction, InteractionTrigger
from app.models.user import User

logger = logging.getLogger("rasheed.agent")

# قديش رسالة نرجع لورا بالمحادثة — كافي للترابط المنطقي، وما بيخلي الطلب
# يكبر ويصير مكلف أكتر من اللازم (كل رسالة إضافية = توكنز إضافية بكل طلب جديد)
CHAT_HISTORY_LIMIT = 20


def _get_recent_history(db: Session, user: User) -> list[ConversationTurn]:
    """
    يجيب آخر N رسالة (بالاتجاهين: من المستخدم ومن رشيد) بالترتيب الزمني الصحيح.
    منجيبهم بترتيب تنازلي (الأحدث أول) عشان الـ LIMIT ياخذ آخر رسائل فعليًا،
    وبعدين نعكس الترتيب عشان نرجعهم زمنيًا صح (الأقدم أول) — هيك لازم يوصلوا
    لـ Gemini، وإلا المحادثة رح تبان مقلوبة له.
    """
    interactions = (
        db.query(AgentInteraction)
        .filter(
            AgentInteraction.user_id == user.id,
            AgentInteraction.trigger_type.in_([InteractionTrigger.USER_CHAT, InteractionTrigger.NUDGE]),
        )
        .order_by(AgentInteraction.created_at.desc())
        .limit(CHAT_HISTORY_LIMIT)
        .all()
    )
    interactions.reverse()
    return [
        ConversationTurn(is_from_user=i.is_from_user, text=i.message)
        for i in interactions
    ]


def send_message_to_agent(db: Session, user: User, message: str) -> str:
    if user.persona is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لازم تخلّص الـ Onboarding وتختار شخصية رشيد قبل ما تحكي معه",
        )

    mood = compute_mood_state(db, user)
    full_system_prompt = build_full_system_prompt(user, mood.state.value, mood.reason)

    # نجيب تاريخ المحادثة *قبل* ما نضيف رسالة المستخدم الحالية لقاعدة البيانات —
    # وإلا رح نرسلها لـ Gemini مرتين (مرة بالـ history ومرة كـ user_message الحالية)
    history = _get_recent_history(db, user)

    provider = get_ai_provider()
    reply = provider.generate_reply(full_system_prompt, message, history=history)

    # نسجّل التفاعل بغض النظر عن نجاح أو فشل الاتصال بالـ AI — مفيد للتصحيح ولاحقًا لتحسين رشيد
    db.add(AgentInteraction(
        user_id=user.id, trigger_type=InteractionTrigger.USER_CHAT,
        message=message, is_from_user=True,
    ))
    db.add(AgentInteraction(
        user_id=user.id, trigger_type=InteractionTrigger.USER_CHAT,
        message=reply.text, is_from_user=False,
    ))
    db.commit()

    if reply.raw_error:
        logger.error("Gemini provider error for user %s: %s", user.id, reply.raw_error)

    return reply.text
