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

GOAL_PROPOSAL_PATTERN = re.compile(r"<<<GOAL_PROPOSAL>>>(.*?)<<<END>>>", re.DOTALL)
ESSENTIALS_UPDATE_PATTERN = re.compile(r"<<<ESSENTIALS_UPDATE>>>(.*?)<<<END>>>", re.DOTALL)
# جديد: بروتوكول تسجيل دخل ذكره المستخدم بالمحادثة (بدل ما ينفهم غلط كهدف جديد)
INCOME_LOG_PATTERN = re.compile(r"<<<INCOME_LOG_PROPOSAL>>>(.*?)<<<END>>>", re.DOTALL)

GOAL_CREATION_PROTOCOL_INSTRUCTIONS = """
قدرة إضافية عندك بهاي المحادثة: تقدر تقترح إنشاء هدف مالي كامل، أو تسجيل
دخل استلمه المستخدم فعليًا. **الفرق بينهم مهم جدًا ولازم تميّزه صح:**

--- الحالة 1: المستخدم بيوصف مصاريف/التزامات قادمة (هدف مستقبلي) ---
مثال: "بدي 200 دينار ملابس شتوية، وراح احلق 5 مرات (30 دينار)، واشتراك جيم
60 دينار خلال 3 شهور". هون بتبني اقتراح هدف:
1. اجمع كل الأرقام الواضحة يلي ذكرها المستخدم.
2. لو احتجت مصاريف أساسية غير مذكورة، استخدم السياق المالي المعطى لك، أو
   اسأل المستخدم مباشرة لو "غير متوفر" (وعند إجابته ضمّن حينها كتلة
   <<<ESSENTIALS_UPDATE>>>{"monthly_estimate": <رقم>}<<<END>>>).
3. لما يصير عندك أرقام كافية، ضمّن بالرد كتلة:
   <<<GOAL_PROPOSAL>>>{"title": "...", "target_amount": <رقم>, "breakdown": [...], "is_recurring": <true أو false>}<<<END>>>

**متى تحط "is_recurring": true؟** بس لما يكون كلام المستخدم عن التزام
شهري متكرر (إيجار، اشتراك، قسط) — مو مبلغ لمرة وحدة. أمثلة تستاهل
is_recurring=true: "بدي أخصص لإيجار البيت كل شهر 150 دينار"، "عندي
اشتراك نت شهري 15 دينار بدي أرصده". أمثلة عادية (is_recurring=false،
أو ما تذكرها أصلاً وبترجع false افتراضيًا): "بدي 200 دينار ملابس
لنهاية السنة" (مرة وحدة، مش شهري).

--- الحالة 2: المستخدم بيخبرك إنه استلم مبلغ فعليًا (دخل حقيقي حصل) ---
مثال: "اشتغلت اليوم واجاني 25 دينار" أو "استلمت راتبي 300 دينار".
**هاي مو هدف جديد إطلاقًا — هاي معاملة دخل لازم تُسجَّل.** ضمّن بالرد كتلة:
<<<INCOME_LOG_PROPOSAL>>>{"amount": <رقم>, "note": "وصف قصير مبني على كلام المستخدم"}<<<END>>>

**قاعدة صارمة: لا تستخدم <<<GOAL_PROPOSAL>>> أبدًا لمجرد إنه المستخدم ذكر
رقم مرتبط بدخل استلمه أو راح يستلمه — هاي حالة تسجيل دخل بس، مش هدف.**
لو مو واضح إذا الكلام عن دخل استلمه أو مصروف مستقبلي يخطط له، اسأله
مباشرة بدل ما تخمّن وتستخدم أي كتلة.

بكل الحالات: الرد الطبيعي المرافق للكتلة لازم يشرح للمستخدم بلغة بسيطة
شو جهزت له (بدون ذكر كلمة JSON أو أي تفاصيل تقنية)، وما تستخدم أي كتلة
إلا لما تكون واثق فعليًا من الأرقام والنية.
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
    user.estimated_monthly_essentials = monthly_estimate
    db.commit()


def _handle_goal_proposal(db: Session, user: User, data: dict, reasoning: str) -> None:
    title = data.get("title")
    target_amount = data.get("target_amount")
    breakdown = data.get("breakdown", [])
    is_recurring = bool(data.get("is_recurring", False))

    if not title or not isinstance(target_amount, (int, float)) or target_amount <= 0:
        logger.warning("Incomplete goal proposal from AI, ignoring: %r", data)
        return

    agent_action_service.create_pending_action(
        db, user,
        action_type="suggest_goal_creation",
        payload={
            "title": title,
            "target_amount": float(target_amount),
            "breakdown": breakdown,
            "is_recurring": is_recurring,
        },
        reasoning=reasoning,
    )


def _handle_income_log_proposal(db: Session, user: User, data: dict, reasoning: str) -> None:
    amount = data.get("amount")
    note = data.get("note", "")

    if not isinstance(amount, (int, float)) or amount <= 0:
        logger.warning("Incomplete income log proposal from AI, ignoring: %r", data)
        return

    agent_action_service.create_pending_action(
        db, user,
        action_type="suggest_income_log",
        payload={"amount": float(amount), "note": note},
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

        # هون كان السبب الجذري: كنا نستدعي _handle_income_log_proposal() بـ
        # reasoning مأخوذ من raw_reply_text فور ما نشيل كتلة الدخل بس —
        # بس لسا كتلة GOAL_PROPOSAL (لو موجودة بنفس الرد، زي لما رشيد يسجل
        # دخل ويقترح هدف بنفس الرسالة) ما انشالت بعد، فالنص الخام لكتلة
        # الهدف كان يتسرب حرفيًا جوا reasoning اقتراح الدخل المعروض للمستخدم.
        # الحل: نشيل كل الكتل أول، وبعدين نستخدم نفس النص النظيف الواحد
        # كـ reasoning لأي اقتراح نتج، مهما كان عددهم بنفس الرد.
        income_data, raw_reply_text = _extract_and_strip_block(INCOME_LOG_PATTERN, raw_reply_text)
        goal_data, raw_reply_text = _extract_and_strip_block(GOAL_PROPOSAL_PATTERN, raw_reply_text)

        if income_data:
            _handle_income_log_proposal(db, user, income_data, reasoning=raw_reply_text[:300])
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
