"""
تقرير مقاييس النجاح (R08) — تجميعي فقط، ما بيعرض أي مستخدم بشكل فردي.

كل المقاييس بتنحسب من الجداول الموجودة أصلًا (users, goals, transactions, agent_interactions, agent_actions,
income_allocations) + جدول user_active_days الصغير للعودة للاستخدام. التعريفات الكاملة بـ docs/METRICS.md.

ملاحظة أداء: بيحمّل الصفوف الخفيفة لذاكرة بايثون ويجمّعها هناك. مناسب لآلاف المستخدمين؛ لو كبّرنا أكتر
بننقل التجميع لاستعلامات SQL.
"""
import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.active_day import UserActiveDay
from app.models.agent import AgentAction, AgentActionStatus, AgentInteraction
from app.models.goal import Goal, GoalStatus
from app.models.income_allocation import IncomeAllocation
from app.models.persona import Persona
from app.models.persona_feedback import PersonaFeedback
from app.models.transaction import Transaction
from app.models.user import User
from app.services.usage_service import local_day

RETENTION_WINDOWS = (1, 7, 30)
TAG_LABELS = {
    "helpful": "مفيد", "friendly": "أسلوبه حلو", "motivating": "بيحمّس",
    "too_long": "طويل زيادة", "too_pushy": "ضاغط زيادة", "confusing": "مش واضح",
}
SMALL_SAMPLE = 10


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _rate(count: int, total: int) -> float | None:
    return round(100 * count / total, 1) if total else None


def build_report(db: Session, *, days: int = 30, now: datetime | None = None, exclude_phones=()) -> dict:
    now = now or datetime.now(timezone.utc)
    excluded = set(exclude_phones)

    all_users = db.query(User).all()
    users = [u for u in all_users if u.phone not in excluded]
    excluded_accounts = len(all_users) - len(users)
    user_ids = {u.id for u in users}
    created = {u.id: _aware(u.created_at) for u in users}

    goals = [g for g in db.query(Goal).all() if g.user_id in user_ids]
    first_transaction: dict = {}
    for user_id, created_at in db.query(Transaction.user_id, Transaction.created_at).all():
        if user_id in user_ids:
            moment = _aware(created_at)
            if user_id not in first_transaction or moment < first_transaction[user_id]:
                first_transaction[user_id] = moment
    chat_users = {
        uid for (uid,) in db.query(AgentInteraction.user_id).filter(AgentInteraction.is_from_user.is_(True)).all()
        if uid in user_ids
    }
    actions = [a for a in db.query(AgentAction).all() if a.user_id in user_ids]
    confirmed_users = {a.user_id for a in actions if a.status == AgentActionStatus.APPLIED}
    allocation_users = {
        uid for (uid,) in db.query(Transaction.user_id)
        .join(IncomeAllocation, IncomeAllocation.transaction_id == Transaction.id).distinct().all()
        if uid in user_ids
    }
    active_days: dict = {}
    for user_id, day in db.query(UserActiveDay.user_id, UserActiveDay.day).all():
        if user_id in user_ids:
            active_days.setdefault(user_id, set()).add(day)

    # ------------------------------------------------------------ مسار التفعيل (لمستخدمي آخر N يوم)
    since = now - timedelta(days=days)
    cohort = [u for u in users if created[u.id] >= since]
    goal_users = {g.user_id for g in goals}
    hours_to_first = [
        max(0.0, (first_transaction[u.id] - created[u.id]).total_seconds() / 3600)
        for u in cohort if u.id in first_transaction
    ]
    cohort_size = len(cohort)
    funnel = {
        "registered": cohort_size,
        "completed_onboarding": sum(1 for u in cohort if u.has_completed_onboarding),
        "created_goal": sum(1 for u in cohort if u.id in goal_users),
        "logged_transaction": sum(1 for u in cohort if u.id in first_transaction),
        "chatted": sum(1 for u in cohort if u.id in chat_users),
        "confirmed_suggestion": sum(1 for u in cohort if u.id in confirmed_users),
        "activated_within_24h": sum(1 for hours in hours_to_first if hours <= 24),
        "median_hours_to_first_transaction": round(statistics.median(hours_to_first), 1) if hours_to_first else None,
    }
    funnel_rates = {key: _rate(value, cohort_size) for key, value in funnel.items()
                    if key not in ("registered", "median_hours_to_first_transaction")}

    # ------------------------------------------------------------------------- العودة للاستخدام
    today = local_day(now)
    retention = {}
    for window in RETENTION_WINDOWS:
        eligible, returned = 0, 0
        for u in users:
            signup_day = local_day(created[u.id])
            if signup_day + timedelta(days=window) > today:
                continue  # لسا ما "نضج" هالمستخدم لهالنافذة
            eligible += 1
            days_seen = active_days.get(u.id, set())
            if any(signup_day < d <= signup_day + timedelta(days=window) for d in days_seen):
                returned += 1
        retention[f"d{window}"] = {"eligible": eligible, "returned": returned, "rate": _rate(returned, eligible)}

    last_7 = {today - timedelta(days=i) for i in range(7)}
    last_30 = {today - timedelta(days=i) for i in range(30)}
    wau = sum(1 for d in active_days.values() if d & last_7)
    mau = sum(1 for d in active_days.values() if d & last_30)
    active_rows_30 = sum(len(d & last_30) for d in active_days.values())
    engagement = {
        "wau": wau,
        "mau": mau,
        "avg_dau_30d": round(active_rows_30 / 30, 2),
        "stickiness_percent": _rate(active_rows_30 / 30, mau) if mau else None,
        "avg_active_days_per_monthly_user": round(active_rows_30 / mau, 1) if mau else None,
    }

    # -------------------------------------------------------------------- النتائج (هل بيوفّر المستخدمين؟)
    progress = [float(g.current_amount) / float(g.target_amount) * 100 for g in goals if float(g.target_amount) > 0]
    outcomes = {
        "users_with_goal": len(goal_users),
        "goals_total": len(goals),
        "goals_achieved": sum(1 for g in goals if g.status == GoalStatus.ACHIEVED),
        "total_target_jod": round(sum(float(g.target_amount) for g in goals), 2),
        "total_saved_jod": round(sum(float(g.current_amount) for g in goals), 2),
        "avg_goal_progress_percent": round(statistics.mean(progress), 1) if progress else None,
        "users_who_allocated_income": len(allocation_users),
        "users_who_allocated_income_percent": _rate(len(allocation_users), len(users)),
    }

    applied = sum(1 for a in actions if a.status == AgentActionStatus.APPLIED)
    rejected = sum(1 for a in actions if a.status == AgentActionStatus.REJECTED)
    agent = {
        "suggestions_total": len(actions),
        "applied": applied,
        "rejected": rejected,
        "pending": len(actions) - applied - rejected,
        "acceptance_rate_percent": _rate(applied, applied + rejected),
    }

    # ---------------------------------------------------------- مقارنة الشخصيات (R13)
    feedback_rows = [f for f in db.query(PersonaFeedback).all() if f.user_id in user_ids]
    personas = []
    for persona in db.query(Persona).order_by(Persona.created_at).all():
        ratings = [f.rating for f in feedback_rows if f.persona_id == persona.id]
        tag_counts: dict = {}
        for f in feedback_rows:
            if f.persona_id == persona.id:
                for tag in f.tags or []:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        personas.append({
            "key": persona.key,
            "name": persona.display_name,
            "users_now": sum(1 for u in users if u.persona_id == persona.id),
            "ratings": len(ratings),
            "avg_rating": round(statistics.mean(ratings), 2) if ratings else None,
            "positive_percent": _rate(sum(1 for r in ratings if r >= 4), len(ratings)),
            "top_tags": sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:3],
        })

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "window_days": days,
        "users_total": len(users),
        "excluded_accounts": excluded_accounts,
        "cohort_small": cohort_size < SMALL_SAMPLE,
        "funnel": funnel,
        "funnel_rates": funnel_rates,
        "retention": retention,
        "engagement": engagement,
        "outcomes": outcomes,
        "agent": agent,
        "personas": personas,
    }


def _fmt(value, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # 100.0 → 100
    return f"{value}{suffix}"


def render_markdown(report: dict) -> str:
    funnel, rates = report["funnel"], report["funnel_rates"]
    lines = [
        "# تقرير مقاييس نجاح رشيد",
        "",
        f"- تاريخ التوليد: {report['generated_at']}",
        f"- إجمالي المستخدمين: **{report['users_total']}**"
        + (f" (بعد استبعاد {report['excluded_accounts']} حساب عرض/اختبار)" if report["excluded_accounts"] else ""),
        f"- نافذة مسار التفعيل: آخر **{report['window_days']}** يوم",
        "",
    ]
    if report["cohort_small"]:
        lines += [
            f"> ⚠️ **عينة صغيرة:** عدد المسجّلين بالنافذة ({funnel['registered']}) أقل من {SMALL_SAMPLE}.",
            "> النسب هون إرشادية فقط وما بتصلح كدليل إحصائي. لا تقدّمها لجهة خارجية كإثبات.",
            "",
        ]

    lines += [
        "## 1. مسار التفعيل (المسجّلون خلال النافذة)",
        "",
        "| المرحلة | العدد | النسبة |",
        "|---|---|---|",
        f"| سجّل حساب | {funnel['registered']} | {'100%' if funnel['registered'] else '—'} |",
        f"| أكمل الـ Onboarding | {funnel['completed_onboarding']} | {_fmt(rates['completed_onboarding'], '%')} |",
        f"| أنشأ هدفًا | {funnel['created_goal']} | {_fmt(rates['created_goal'], '%')} |",
        f"| سجّل أول معاملة | {funnel['logged_transaction']} | {_fmt(rates['logged_transaction'], '%')} |",
        f"| سجّل أول معاملة خلال 24 ساعة | {funnel['activated_within_24h']} | {_fmt(rates['activated_within_24h'], '%')} |",
        f"| تحدّث مع رشيد | {funnel['chatted']} | {_fmt(rates['chatted'], '%')} |",
        f"| وافق على اقتراح من رشيد | {funnel['confirmed_suggestion']} | {_fmt(rates['confirmed_suggestion'], '%')} |",
        "",
        f"الوقت الوسيط لأول معاملة: **{_fmt(funnel['median_hours_to_first_transaction'], ' ساعة')}**",
        "",
        "## 2. العودة للاستخدام (كل المستخدمين الذين نضجوا للنافذة)",
        "",
        "> D1 / D7 / D30 = المستخدم رجع وفتح التطبيق خلال 1 / 7 / 30 يوم بعد يوم تسجيله. "
        "بنحسب فقط المستخدمين اللي عدّى عليهم هالعدد من الأيام.",
        "",
        "| النافذة | عادوا | المؤهّلون | النسبة |",
        "|---|---|---|---|",
    ]
    for window in RETENTION_WINDOWS:
        item = report["retention"][f"d{window}"]
        lines.append(
            f"| D{window} | {item['returned']} | {item['eligible']} | {_fmt(item['rate'], '%')} |"
        )

    engagement = report["engagement"]
    outcomes = report["outcomes"]
    agent = report["agent"]
    lines += [
        "",
        "## 3. النشاط",
        "",
        f"- مستخدمون نشطون آخر 7 أيام (WAU): **{engagement['wau']}**",
        f"- مستخدمون نشطون آخر 30 يوم (MAU): **{engagement['mau']}**",
        f"- متوسط النشطين يوميًا (آخر 30 يوم): **{engagement['avg_dau_30d']}**",
        f"- الالتصاق (متوسط DAU ÷ MAU): **{_fmt(engagement['stickiness_percent'], '%')}**",
        f"- متوسط أيام النشاط لكل مستخدم شهري: **{_fmt(engagement['avg_active_days_per_monthly_user'])}**",
        "",
        "## 4. النتائج: هل بيوفّر المستخدمون؟",
        "",
        f"- مستخدمون لديهم هدف: **{outcomes['users_with_goal']}** ({outcomes['goals_total']} هدف، "
        f"{outcomes['goals_achieved']} منها محقَّق)",
        f"- إجمالي المستهدف: **{_fmt(outcomes['total_target_jod'])}** دينار، "
        f"والمدّخر فعليًا: **{_fmt(outcomes['total_saved_jod'])}** دينار",
        f"- متوسط تقدّم الأهداف: **{_fmt(outcomes['avg_goal_progress_percent'], '%')}**",
        f"- مستخدمون وزّعوا دخلهم على أهدافهم: **{outcomes['users_who_allocated_income']}** "
        f"({_fmt(outcomes['users_who_allocated_income_percent'], '%')} من كل المستخدمين)",
        "",
        "## 5. ثقة المستخدمين برشيد",
        "",
        f"- اقتراحات رشيد: **{agent['suggestions_total']}** (وافق **{agent['applied']}**، رفض **{agent['rejected']}**، "
        f"معلّق **{agent['pending']}**)",
        f"- نسبة القبول: **{_fmt(agent['acceptance_rate_percent'], '%')}**",
        "",
        "## 6. مقارنة شخصيات رشيد",
        "",
        "| الشخصية | مستخدمون حاليًا | عدد التقييمات | متوسط التقييم | 4-5 نجوم | أكثر الوسوم |",
        "|---|---|---|---|---|---|",
    ]
    for persona in report["personas"]:
        tags = "، ".join(f"{TAG_LABELS.get(tag, tag)} ({count})" for tag, count in persona["top_tags"]) or "—"
        lines.append(
            f"| {persona['name']} | {persona['users_now']} | {persona['ratings']} | "
            f"{_fmt(persona['avg_rating'])} | {_fmt(persona['positive_percent'], '%')} | {tags} |"
        )
    lines += [
        "",
        "> التقييم ذاتي، وكل مستخدم بيقدر يبدّل ويقيّم أكتر من شخصية، والعينة غالبًا صغيرة. استخدمه كمؤشر أولي فقط.",
        "",
        "---",
        "تعريفات المقاييس وحدودها: `docs/METRICS.md`. التقرير تجميعي ولا يعرض أي مستخدم بشكل فردي.",
    ]
    return "\n".join(lines) + "\n"
