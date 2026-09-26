"""
Agent Action Service — رشيد يقترح تعديلات فعلية على بيانات المستخدم،
وينفذها بس بعد موافقة صريحة (نفس مبدأ الأمان يلي حددناه بـ Sprint 0:
أي اقتراح يبدأ بحالة PENDING، وما ينفّذ فعليًا إلا بعد /confirm صريح).

نمط التوليد: نفس فلسفة nudge_service بالضبط — منطق Rule-based بسيط يقرر
"متى" نقترح (فحص دوري)، والـ AI بيستخدم بس لتحديد "شو بالضبط" نقترح
بالحالة يلي فعليًا محتاجة ذكاء (تصنيف نص حر). اقتراح المساهمة بالهدف
Rule-based بالكامل، ما بيحتاج AI أصلاً.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.agent.mood_engine import compute_mood_state, MoodState
from app.agent.providers.factory import get_ai_provider
from app.models.agent import AgentAction, AgentActionType, AgentActionStatus
from app.models.transaction import Transaction, TransactionType, TransactionSource
from app.models.category import Category
from app.models.goal import Goal, GoalStatus
from app.models.user import User
from app.services import goal_service

logger = logging.getLogger("rasheed.agent")

SUGGESTION_LOOKBACK_DAYS = 7
MAX_CATEGORY_SUGGESTIONS_PER_CHECK = 3  # ما نغرق المستخدم باقتراحات كثيرة مرة وحدة
GOAL_CONTRIBUTION_RATIO = 0.2  # نقترح إكمال 20% من المتبقي على الهدف


# ---------- عرض وإدارة الاقتراحات ----------

def list_pending_actions(db: Session, user: User) -> list[AgentAction]:
    return (
        db.query(AgentAction)
        .filter(AgentAction.user_id == user.id, AgentAction.status == AgentActionStatus.PENDING)
        .order_by(AgentAction.created_at.desc())
        .all()
    )


def _get_pending_action_or_404(db: Session, user: User, action_id: UUID) -> AgentAction:
    action = (
        db.query(AgentAction)
        .filter(AgentAction.id == action_id, AgentAction.user_id == user.id)
        .first()
    )
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الاقتراح غير موجود")
    if action.status != AgentActionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="هذا الاقتراح تم الرد عليه مسبقًا",
        )
    return action


def reject_action(db: Session, user: User, action_id: UUID) -> AgentAction:
    action = _get_pending_action_or_404(db, user, action_id)
    action.status = AgentActionStatus.REJECTED
    db.commit()
    db.refresh(action)
    return action


def create_pending_action(
    db: Session, user: User, action_type: str, payload: dict, reasoning: str | None = None
) -> AgentAction:
    """
    دالة مشتركة لإنشاء اقتراح PENDING جديد — تُستخدم من هالملف نفسه
    (اقتراحات دورية) ومن agent_chat_service (اقتراحات مبنية على محادثة حرة
    مع رشيد، مثل اقتراح هدف كامل بـ Sprint 5). مكان واحد لإنشاء أي اقتراح
    بغض النظر عن مصدره.
    """
    action = AgentAction(
        user_id=user.id,
        action_type=AgentActionType(action_type),
        payload=payload,
        reasoning=reasoning,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def confirm_action(db: Session, user: User, action_id: UUID) -> AgentAction:
    """
    ينفّذ الاقتراح فعليًا على قاعدة البيانات — هاي الدالة الوحيدة بكل
    المشروع يلي فيها "رشيد يطبّق شي فعلي"، ومحصورة بمكان واحد واضح
    وسهل المراجعة (مهم جدًا لأي كود بيلمس بيانات مالية).
    """
    action = _get_pending_action_or_404(db, user, action_id)

    if action.action_type == AgentActionType.SUGGEST_CATEGORY_CORRECTION:
        _apply_category_correction(db, user, action)
    elif action.action_type == AgentActionType.SUGGEST_GOAL_CONTRIBUTION:
        _apply_goal_contribution(db, user, action)
    elif action.action_type == AgentActionType.SUGGEST_GOAL_CREATION:
        _apply_goal_creation(db, user, action)
    elif action.action_type == AgentActionType.SUGGEST_INCOME_LOG:
        _apply_income_log(db, user, action)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="نوع اقتراح غير مدعوم")

    action.status = AgentActionStatus.APPLIED
    db.commit()
    db.refresh(action)
    return action


def _apply_category_correction(db: Session, user: User, action: AgentAction) -> None:
    # الـ payload عمود JSON، فالـ UUIDs مخزّنة فيه كنص عادي (str) —
    # لازم نحوّلهم لـ UUID حقيقي قبل أي استعلام أو تعيين قيمة، وإلا SQLAlchemy
    # بيطلع خطأ (بعض قواعد البيانات بتتساهل، وبعضها لأ — الصح نحوّل دايمًا).
    try:
        transaction_id = UUID(action.payload.get("transaction_id"))
        new_category_id = UUID(action.payload.get("new_category_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="بيانات الاقتراح تالفة")

    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == user.id)
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المعاملة الأصلية غير موجودة")

    transaction.category_id = new_category_id


def _apply_goal_contribution(db: Session, user: User, action: AgentAction) -> None:
    try:
        goal_id = UUID(action.payload.get("goal_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="بيانات الاقتراح تالفة")

    amount = action.payload.get("amount")

    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الهدف غير موجود")

    goal.current_amount = float(goal.current_amount) + float(amount)
    if float(goal.current_amount) >= float(goal.target_amount):
        goal.status = GoalStatus.ACHIEVED


def _apply_goal_creation(db: Session, user: User, action: AgentAction) -> None:
    title = action.payload.get("title")
    target_amount = action.payload.get("target_amount")
    is_recurring = bool(action.payload.get("is_recurring", False))

    if not title or not isinstance(target_amount, (int, float)) or target_amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="بيانات الاقتراح تالفة")

    goal = Goal(
        user_id=user.id,
        title=title,
        target_amount=target_amount,
        # priority: نفس منطق الإنشاء اليدوي بالضبط — آخر الترتيب، مش 0 دايمًا،
        # عشان ما تتصادم كل الأهداف الجاية من الشات بنفس الأولوية قبل أول ترتيب يدوي.
        priority=goal_service._next_priority_for_user(db, user),
        is_recurring=is_recurring,
        last_reset_month=goal_service._current_month_key() if is_recurring else None,
        # current_amount تبدأ 0 افتراضيًا — الهدف هون تخطيطي، المستخدم بيبلش
        # يسجّل تقدمه فيه لاحقًا عبر التسجيل السريع أو اقتراحات المساهمة
    )
    db.add(goal)


def _apply_income_log(db: Session, user: User, action: AgentAction) -> None:
    # هذا بالضبط كان السبب الجذري لـ Bug 1: هذا النوع من الاقتراح كان موجود
    # بالـ Enum ويتولّد صح من الشات، بس confirm_action() ما كان فيها حالة
    # تتعامل معه أصلاً — فكان بيوقع على else ويرجّع 400 دايمًا، بغض النظر
    # عن صحة البيانات. مش خطأ بالقيمة أو النوع، كان نقص كامل بالتنفيذ.
    amount = action.payload.get("amount")
    note = action.payload.get("note")

    if not isinstance(amount, (int, float)) or amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="بيانات الاقتراح تالفة")

    transaction = Transaction(
        user_id=user.id,
        category_id=None,
        amount=amount,
        type=TransactionType.INCOME,
        source=TransactionSource.MANUAL,
        note=note,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(transaction)


# ---------- توليد اقتراحات جديدة ----------

def generate_suggestions(db: Session, user: User) -> list[AgentAction]:
    """
    يُستدعى دوريًا من الموبايل (مثلاً عند فتح شاشة الاقتراحات أو الـ Dashboard).
    يفحص وضع المستخدم الحالي ويولّد اقتراحات جديدة لو في داعي فعلي —
    قد يرجّع قائمة فاضية، وهذا رد طبيعي متوقع مش خطأ.
    """
    new_actions: list[AgentAction] = []
    new_actions.extend(_suggest_category_corrections(db, user))
    new_actions.extend(_suggest_goal_contribution(db, user))
    return new_actions


def _suggest_category_corrections(db: Session, user: User) -> list[AgentAction]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=SUGGESTION_LOOKBACK_DAYS)

    uncategorized = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            Transaction.category_id.is_(None),
            Transaction.note.isnot(None),
            Transaction.occurred_at >= cutoff,
        )
        .order_by(Transaction.occurred_at.desc())
        .limit(MAX_CATEGORY_SUGGESTIONS_PER_CHECK)
        .all()
    )
    if not uncategorized:
        return []

    # ما نكرر اقتراح لمعاملة عندها اقتراح PENDING أصلاً من فحص سابق
    already_suggested_ids = {
        a.payload.get("transaction_id")
        for a in db.query(AgentAction).filter(
            AgentAction.user_id == user.id,
            AgentAction.action_type == AgentActionType.SUGGEST_CATEGORY_CORRECTION,
            AgentAction.status == AgentActionStatus.PENDING,
        )
    }

    categories = (
        db.query(Category)
        .filter((Category.is_default.is_(True)) | (Category.user_id == user.id))
        .all()
    )
    category_lookup = {str(c.id): c.name for c in categories}
    if not category_lookup:
        return []

    provider = get_ai_provider()
    created: list[AgentAction] = []

    for transaction in uncategorized:
        if str(transaction.id) in already_suggested_ids:
            continue

        suggestion = _ask_ai_for_category(provider, transaction, category_lookup)
        if suggestion is None:
            continue

        category_id, reasoning = suggestion
        action = AgentAction(
            user_id=user.id,
            action_type=AgentActionType.SUGGEST_CATEGORY_CORRECTION,
            payload={
                "transaction_id": str(transaction.id),
                "new_category_id": category_id,
                "new_category_name": category_lookup[category_id],
                "transaction_note": transaction.note,
                "transaction_amount": float(transaction.amount),
            },
            reasoning=reasoning,
        )
        db.add(action)
        created.append(action)

    if created:
        db.commit()
        for a in created:
            db.refresh(a)
    return created


def _ask_ai_for_category(
    provider, transaction: Transaction, category_lookup: dict[str, str]
) -> tuple[str, str] | None:
    """يرجّع (category_id, reasoning) لو رشيد قدر يقترح تصنيف صالح، أو None لو لأ."""
    category_options = "\n".join(f"- {cid}: {name}" for cid, name in category_lookup.items())
    prompt = (
        f'معاملة مالية بدون تصنيف، وصفها: "{transaction.note or ""}"\n'
        f"المبلغ: {transaction.amount}\n\n"
        f"التصنيفات المتاحة (id: اسم):\n{category_options}\n\n"
        'اختر أنسب تصنيف id لهاي المعاملة. رد فقط بصيغة JSON صحيحة على هذا الشكل بالضبط، '
        'بدون أي نص إضافي قبله أو بعده: {"category_id": "...", "reasoning": "سبب مختصر بجملة وحدة"}'
    )

    reply = provider.generate_reply(
        system_prompt="أنت مساعد تصنيف بيانات مالية دقيق. رد بصيغة JSON فقط، بدون أي نص إضافي.",
        user_message=prompt,
    )
    if reply.raw_error:
        logger.error("Category suggestion AI call failed: %s", reply.raw_error)
        return None

    # نتحمّل إنه بعض النماذج بترجع الـ JSON ملفوف بـ ```json ... ``` رغم التعليمات الصريحة
    cleaned = reply.text.strip().strip("`").removeprefix("json").strip()

    try:
        parsed = json.loads(cleaned)
        category_id = parsed["category_id"]
        reasoning = parsed.get("reasoning", "")
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.error("Could not parse category suggestion JSON: %r", reply.text)
        return None

    if category_id not in category_lookup:
        # رشيد اقترح id مش موجود فعليًا بقائمتنا — نتجاهل الاقتراح بدل ما نخزن بيانات فاسدة
        logger.warning("AI suggested unknown category_id: %r", category_id)
        return None

    return category_id, reasoning


def _suggest_goal_contribution(db: Session, user: User) -> list[AgentAction]:
    mood = compute_mood_state(db, user)
    if mood.state != MoodState.ENERGIZED:
        return []  # نقترح مساهمة بس لما المستخدم بوضع جيد فعليًا، مش لما يكون قلقان

    active_goal = (
        db.query(Goal)
        .filter(Goal.user_id == user.id, Goal.status == GoalStatus.ACTIVE)
        .order_by(Goal.created_at.desc())
        .first()
    )
    if active_goal is None:
        return []

    existing_pending = (
        db.query(AgentAction)
        .filter(
            AgentAction.user_id == user.id,
            AgentAction.action_type == AgentActionType.SUGGEST_GOAL_CONTRIBUTION,
            AgentAction.status == AgentActionStatus.PENDING,
        )
        .first()
    )
    if existing_pending is not None:
        return []

    remaining = float(active_goal.target_amount) - float(active_goal.current_amount)
    if remaining <= 0:
        return []

    # منطق مبدئي بسيط (Rule-based) — نقترح إكمال نسبة من المتبقي.
    # قابل للتحسين لاحقًا ليعتمد على دخل المستخدم الفعلي ونمط توفيره،
    # بدل نسبة ثابتة للجميع.
    suggested_amount = round(remaining * GOAL_CONTRIBUTION_RATIO, 2)
    if suggested_amount <= 0:
        return []

    action = AgentAction(
        user_id=user.id,
        action_type=AgentActionType.SUGGEST_GOAL_CONTRIBUTION,
        payload={
            "goal_id": str(active_goal.id),
            "goal_title": active_goal.title,
            "amount": suggested_amount,
        },
        reasoning=(
            f"إنت قريب من هدف '{active_goal.title}' ({active_goal.progress_percentage}%)! "
            f"{mood.reason}"
        ),
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return [action]
