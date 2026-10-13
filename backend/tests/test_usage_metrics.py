"""
R08 — قياس نجاح المنتج بأقل بيانات: يوم النشاط، مسار التفعيل، العودة للاستخدام، النتائج، والخصوصية.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models.active_day import UserActiveDay
from app.models.agent import AgentAction, AgentActionStatus, AgentActionType, AgentInteraction, InteractionTrigger
from app.models.goal import Goal, GoalStatus
from app.models.income_allocation import IncomeAllocation
from app.models.transaction import Transaction, TransactionSource, TransactionType
from app.models.user import IncomeType, User
from app.services import usage_metrics_service, usage_service
from tests.test_income_and_goal_delete import register_with_persona

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------- يوم النشاط

def active_rows(db_session, user):
    return db_session.query(UserActiveDay).filter(UserActiveDay.user_id == user.id).count()


def test_opening_the_app_records_one_active_day_per_day(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790140001")
    before = active_rows(db_session, user)  # التسجيل نفسه بيسجّل اليوم الأول
    for _ in range(3):
        assert client.get("/api/v1/users/me", headers=headers).status_code == 200
    assert active_rows(db_session, user) == max(before, 1) == 1


def test_login_records_an_active_day(client, db_session):
    _, user = register_with_persona(client, db_session, "0790140002")
    db_session.query(UserActiveDay).delete()
    db_session.commit()
    response = client.post("/api/v1/auth/login", json={"phone": "0790140002", "password": "testpassword123"})
    assert response.status_code == 200
    assert active_rows(db_session, user) == 1


def test_recording_uses_the_configured_local_day(db_session, client, monkeypatch):
    _, user = register_with_persona(client, db_session, "0790140003")
    db_session.query(UserActiveDay).delete()
    db_session.commit()
    monkeypatch.setattr(settings, "ANALYTICS_UTC_OFFSET_HOURS", 3)
    late_night_utc = datetime(2026, 10, 10, 22, 30, tzinfo=timezone.utc)  # 01:30 يوم 11 بتوقيت عمّان

    assert usage_service.record_active_day(db_session, user, now=late_night_utc) is True
    assert db_session.query(UserActiveDay).one().day.isoformat() == "2026-10-11"
    assert usage_service.record_active_day(db_session, user, now=late_night_utc) is False


def test_measurement_failure_never_breaks_the_request(client, db_session, monkeypatch):
    headers, _ = register_with_persona(client, db_session, "0790140004")

    def broken(*args, **kwargs):
        raise RuntimeError("db hiccup")

    monkeypatch.setattr(usage_service, "UserActiveDay", broken)
    assert client.get("/api/v1/users/me", headers=headers).status_code == 200


# ------------------------------------------------------------------ التقرير

def make_user(db_session, phone, days_ago, onboarded=True):
    user = User(
        id=uuid.uuid4(), name=f"اسم-سري-{phone}", phone=phone, hashed_password="x",
        income_type=IncomeType.VARIABLE, has_completed_onboarding=onboarded,
        created_at=NOW - timedelta(days=days_ago),
    )
    db_session.add(user)
    db_session.flush()
    return user


def add_transaction(db_session, user, hours_after_signup):
    tx = Transaction(
        user_id=user.id, amount=10, type=TransactionType.INCOME, source=TransactionSource.MANUAL, note="x",
        occurred_at=user.created_at, created_at=user.created_at + timedelta(hours=hours_after_signup),
    )
    db_session.add(tx)
    db_session.flush()
    return tx


def add_active(db_session, user, *offsets_from_signup):
    base = user.created_at.date()
    for offset in offsets_from_signup:
        db_session.add(UserActiveDay(user_id=user.id, day=base + timedelta(days=offset)))


def scenario(db_session):
    """4 مستخدمين جدد بآخر 30 يوم + مستخدم قديم + حساب العرض التجريبي."""
    a = make_user(db_session, "0790150001", 20)  # كامل المسار
    b = make_user(db_session, "0790150002", 15)  # بدون معاملات
    c = make_user(db_session, "0790150003", 10, onboarded=False)
    d = make_user(db_session, "0790150004", 3)
    old = make_user(db_session, "0790150005", 60)
    demo = make_user(db_session, "0799000000", 5)

    goal = Goal(
        user_id=a.id, title="سفر", icon="x", target_amount=200, current_amount=100, status=GoalStatus.ACTIVE,
    )
    goal2 = Goal(
        user_id=b.id, title="لابتوب", icon="x", target_amount=100, current_amount=100, status=GoalStatus.ACHIEVED,
    )
    db_session.add_all([goal, goal2])
    tx_a = add_transaction(db_session, a, 2)       # خلال 24 ساعة
    add_transaction(db_session, d, 30)             # بعد 24 ساعة
    add_transaction(db_session, demo, 1)           # لازم يتجاهله التقرير
    db_session.flush()
    db_session.add(IncomeAllocation(transaction_id=tx_a.id, goal_id=goal.id, amount=10))
    db_session.add(AgentInteraction(
        user_id=a.id, trigger_type=InteractionTrigger.USER_CHAT, message="سؤال", is_from_user=True,
    ))
    statuses = ((a, AgentActionStatus.APPLIED), (b, AgentActionStatus.REJECTED), (b, AgentActionStatus.PENDING))
    for owner, action_status in statuses:
        db_session.add(AgentAction(
            user_id=owner.id, action_type=AgentActionType.SUGGEST_INCOME_LOG, status=action_status, payload={}, reasoning="x",
        ))
    add_active(db_session, a, 0, 1, 5, 19)         # عاد يوم 1 و7 و30(لا: 19 يوم فقط)
    add_active(db_session, b, 0, 12)               # عاد خلال 7؟ لا (12 يوم)
    add_active(db_session, old, 0, 40)
    db_session.commit()
    return a, b, c, d, old


def report(db_session):
    return usage_metrics_service.build_report(db_session, days=30, now=NOW, exclude_phones=["0799000000"])


def test_funnel_numbers_and_demo_exclusion(db_session):
    scenario(db_session)
    data = report(db_session)

    assert data["users_total"] == 5  # بدون حساب العرض
    funnel = data["funnel"]
    assert funnel["registered"] == 4  # a,b,c,d (القديم خارج نافذة 30 يوم)
    assert funnel["completed_onboarding"] == 3
    assert funnel["created_goal"] == 2
    assert funnel["logged_transaction"] == 2
    assert funnel["activated_within_24h"] == 1
    assert funnel["median_hours_to_first_transaction"] == 16.0  # وسيط 2 و30
    assert funnel["chatted"] == 1 and funnel["confirmed_suggestion"] == 1
    assert data["funnel_rates"]["created_goal"] == 50.0
    assert data["cohort_small"] is True


def test_retention_only_counts_matured_users(db_session):
    scenario(db_session)
    retention = report(db_session)["retention"]

    # D1: مؤهلين: a(20 يوم) b(15) c(10) d(3) old(60) = 5 ؛ عادوا خلال يوم: a فقط (يوم 1)
    assert retention["d1"] == {"eligible": 5, "returned": 1, "rate": 20.0}
    # D7: كلهم مؤهلين (d عمره 3 أيام لسا ما نضج): 4 ؛ عادوا: a (يوم 5)
    assert retention["d7"]["eligible"] == 4 and retention["d7"]["returned"] == 1
    # D30: مؤهل فقط old (60 يوم) وعاد يوم 40 (> 30) → ما احتُسب
    assert retention["d30"] == {"eligible": 1, "returned": 0, "rate": 0.0}


def test_outcomes_and_agent_trust(db_session):
    scenario(db_session)
    data = report(db_session)

    outcomes = data["outcomes"]
    assert outcomes["goals_total"] == 2 and outcomes["goals_achieved"] == 1
    assert outcomes["total_target_jod"] == 300.0 and outcomes["total_saved_jod"] == 200.0
    assert outcomes["avg_goal_progress_percent"] == 75.0
    assert outcomes["users_who_allocated_income"] == 1
    assert data["agent"] == {
        "suggestions_total": 3, "applied": 1, "rejected": 1, "pending": 1, "acceptance_rate_percent": 50.0,
    }


def test_empty_database_produces_a_valid_report(db_session):
    data = usage_metrics_service.build_report(db_session, now=NOW)
    markdown = usage_metrics_service.render_markdown(data)
    assert data["users_total"] == 0 and data["funnel"]["registered"] == 0
    assert "تقرير مقاييس نجاح رشيد" in markdown and "عينة صغيرة" in markdown


def test_report_never_contains_personal_data(db_session):
    scenario(db_session)
    markdown = usage_metrics_service.render_markdown(report(db_session))
    assert "اسم-سري" not in markdown
    assert "07901500" not in markdown and "0799000000" not in markdown
    assert "## 1. مسار التفعيل" in markdown and "## 4. النتائج" in markdown


def test_engagement_counts_recent_activity(db_session):
    scenario(db_session)

    engagement = report(db_session)["engagement"]

    # آخر 7 أيام: a (قبل يوم) وb (قبل 3 أيام). آخر 30 يوم: + old (قبل 20 يوم). مجموع أيام النشاط بالـ 30 يوم = 7
    assert engagement["wau"] == 2 and engagement["mau"] == 3
    assert engagement["avg_dau_30d"] == 0.23
    assert engagement["avg_active_days_per_monthly_user"] == 2.3
