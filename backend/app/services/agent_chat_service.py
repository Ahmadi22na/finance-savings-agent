from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agent.mood_engine import compute_mood_state
from app.agent.providers.factory import get_ai_provider
from app.models.agent import AgentInteraction, InteractionTrigger
from app.models.user import User


def send_message_to_agent(db: Session, user: User, message: str) -> str:
    if user.persona is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لازم تخلّص الـ Onboarding وتختار شخصية رشيد قبل ما تحكي معه",
        )

    mood = compute_mood_state(db, user)

    # نبني الـ System Prompt النهائي: شخصية المستخدم المختارة + سياق حالته المزاجية الحالية
    # + اسمه، عشان رشيد يحس "شخصي" مش عام
    full_system_prompt = (
        f"{user.persona.system_prompt}\n\n"
        f"معلومات إضافية عن المستخدم الحالي (استخدمها بذكاء، ما تكررها حرفيًا):\n"
        f"- اسمه: {user.name}\n"
        f"- حالتك المزاجية الحالية تجاهه: {mood.state.value} — السبب: {mood.reason}"
    )

    provider = get_ai_provider()
    reply = provider.generate_reply(full_system_prompt, message)

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
        # ما نوقف الطلب بخطأ 500 — رشيد "يحكي" حتى لو في مشكلة تقنية خلفه، بس نسجل التفاصيل
        # بـ raw_error لأي حد يراجع الـ Logs لاحقًا (مش شي يشوفه المستخدم)
        pass

    return reply.text
