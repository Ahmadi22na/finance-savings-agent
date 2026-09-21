import json
import logging
import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agent.mood_engine import compute_mood_state, build_full_system_prompt
from app.agent.financial_context import get_essentials_estimate
from app.agent.providers.base import ConversationTurn
from app.agent.providers.factory import get_ai_provider
from app.models.agent import AgentInteraction, InteractionTrigger
from app.models.user import User
from app.services import agent_action_service

logger = logging.getLogger("rasheed.agent")

CHAT_HISTORY_LIMIT = 20

# --- بروتوكول الاقتراحات المضمّنة بالمحادثة (Sprint 5) ---
# رشيد ممكن "يضمّن" داخل ردّه كتلة JSON محاطة بعلامات خاصة، بدل ما نبني
# طبقة Function Calling كاملة من الصفر. الكتلة بتُستخرج وتُحذف من النص
# قبل ما يوصل الرد للمستخدم — هو بس بيشوف النص الطبيعي.
GOAL_PROPOSAL_PATTERN = re.compile(r"<<<GOAL_PROPOSAL>>>(.*?)<<<END>>>", re.DOTALL)
ESSENTIALS_UPDATE_PATTERN = re.compile(r"<<<ESSENTIALS_UPDATE>>>(.*?)<<<END>>>", re.DOTALL)

GOAL_CREATION_PROTOCOL_INSTRUCTIONS = """
قدرة إضافية عندك بهاي المحادثة: تقدر تقترح إنشاء هدف مالي كامل للمستخدم
لو وصف لك مصاريف/التزامات قادمة يعرفها بشكل واضح (حتى لو ما قال رقم هدف
مباشر) — مثال: "بدي 200 دينار ملابس شتوية، وراح احلق 5 مرات (30 دينار)،
واشتراك جيم 60 دينار خلال 3 شهور".

خطوات لازم تتبعها بهيك حالة:
1. اجمع كل الأرقام الواضحة يلي ذكرها المستخدم.
2. المصاريف الأساسية (أكل، مواصلات...) غالبًا ما بينذكروا صراحة — استخدم
   المعلومة المعطاة لك بالسياق (محفوظة، من تاريخه، أو غير متوفرة).
   - لو "غير متوفرة": اسأل المستخدم مباشرة بسؤال طبيعي بسيط، وما تكمل
     الاقتراح لحد ما يجاوبك. لما يجاوبك برقم واضح، ضمّن بنفس الرد كتلة:
     <<<ESSENTIALS_UPDATE>>>{"monthly_estimate": <رقم>}<<<END>>>
     مع رد طبيعي عادي حواليها (المستخدم ما بيشوف هاي الكتلة، بتنحذف تلقائيًا).
3. لما يصير عندك كل الأرقام الكافية لبناء الهدف، ضمّن بنفس ردّك كتلة:
   <<<GOAL_PROPOSAL>>>{"title": "عنوان قصير للهدف", "target_amount": <المجموع الكلي كرقم>, "breakdown": [{"label": "...", "amount": <رقم>}, ...]}<<<END>>>
   مع رد طبيعي تشرح فيه للمستخدم إنك جهّزت اقتراح هدف وينتظر موافقته
   (بدون ما تذكر كلمة "JSON" أو تفاصيل تقنية له إطلاقًا).
4. لا تستخدم هالكتل إلا لما تكون فعليًا واثق من الأرقام — لو المستخدم
   بس بيسأل سؤال عام أو بيحكي عادي، جاوب بشكل طبيعي بدون أي كتلة.
""".strip()


def _get_recent_history(db: Session, user: User) -> list[ConversationTurn]:
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
    return [ConversationTurn(is_from_user=i.is_from_user, text=i.message) for i in interactions]


def _extract_and_strip_block(pattern: re.Pattern, text: str) -> tuple[dict | None, str]:
    """يدوّر عن كتلة البروتوكول، يحاول يفكّها كـ JSON، ويرجّع النص بعد ما يشيلها."""
    match = pattern.search(text)
    if match is None:
        return None, text

    cleaned_text = pattern.sub("", text).strip()
    try:
        data = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        logger.warning("Could not parse protocol block: %r", match.group(1))
        return None, cleaned_text
    return data, cleaned_text


def _handle_essentials_update(db: Session, user: User, data: dict) -> None:
    monthly_estimate = data.get("monthly_estimate")
    if not isinstance(monthly_estimate, (int, float)) or monthly_estimate <= 0:
        return
    # مجرد تسجيل معلومة قالها المستخدم عن نفسه — مش قرار مالي، فما بيحتاج
    # نفس بوابة الموافقة الصريحة يلي الاقتراحات المالية الفعلية بتحتاجها
    user.estimated_monthly_essentials = monthly_estimate
    db.commit()


def _handle_goal_proposal(db: Session, user: User, data: dict, reasoning: str) -> None:
    title = data.get("title")
    target_amount = data.get("target_amount")
    breakdown = data.get("breakdown", [])

    if not title or not isinstance(target_amount, (int, float)) or target_amount <= 0:
        logger.warning("Incomplete goal proposal from AI, ignoring: %r", data)
        return

    agent_action_service.create_pending_action(
        db, user,
        action_type="suggest_goal_creation",
        payload={"title": title, "target_amount": float(target_amount), "breakdown": breakdown},
        reasoning=reasoning,
    )


def send_message_to_agent(db: Session, user: User, message: str) -> str:
    if user.persona is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لازم تخلّص الـ Onboarding وتختار شخصية رشيد قبل ما تحكي معه",
        )

    mood = compute_mood_state(db, user)
    essentials = get_essentials_estimate(db, user)

    full_system_prompt = (
        f"{build_full_system_prompt(user, mood.state.value, mood.reason)}\n\n"
        f"سياق مالي إضافي: {essentials.note}\n\n"
        f"{GOAL_CREATION_PROTOCOL_INSTRUCTIONS}"
    )

    history = _get_recent_history(db, user)

    provider = get_ai_provider()
    reply = provider.generate_reply(full_system_prompt, message, history=history)

    if reply.raw_error:
        logger.error("Gemini provider error for user %s: %s", user.id, reply.raw_error)
        raw_reply_text = reply.text
    else:
        raw_reply_text = reply.text

        essentials_data, raw_reply_text = _extract_and_strip_block(ESSENTIALS_UPDATE_PATTERN, raw_reply_text)
        if essentials_data:
            _handle_essentials_update(db, user, essentials_data)

        goal_data, raw_reply_text = _extract_and_strip_block(GOAL_PROPOSAL_PATTERN, raw_reply_text)
        if goal_data:
            _handle_goal_proposal(db, user, goal_data, reasoning=raw_reply_text[:300])

    db.add(AgentInteraction(
        user_id=user.id, trigger_type=InteractionTrigger.USER_CHAT,
        message=message, is_from_user=True,
    ))
    db.add(AgentInteraction(
        user_id=user.id, trigger_type=InteractionTrigger.USER_CHAT,
        message=raw_reply_text, is_from_user=False,
    ))
    db.commit()

    return raw_reply_text
