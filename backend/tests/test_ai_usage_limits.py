"""
R11 — حدود استهلاك الذكاء الاصطناعي: لكل نوع، لإجمالي المستخدم، عام، نافذة 24 ساعة، تنبيهات، تراجع لطيف.
"""
import logging
from datetime import datetime, timedelta, timezone

import pytest

from app.agent.providers.base import AgentReply
from app.api.routes import transactions as transactions_route
from app.config import settings
from app.models.agent import AgentAction, AgentInteraction
from app.models.ai_usage import AiUsageEvent, AiUsageKind
from app.models.category import Category, CategoryType
from app.models.transaction import Transaction, TransactionSource, TransactionType
from app.services import agent_action_service, ai_usage_service
from app.services.categorizer import factory as categorizer_factory
from app.services.categorizer.gemini_based import GeminiCategorizer
from tests.test_income_and_goal_delete import FakeReplyProvider, patch_provider, register_with_persona

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def default_limits(monkeypatch):
    """حدود معروفة لكل اختبار، بغض النظر عن قيم .env."""
    values = {
        "AI_PROVIDER": "gemini", "AI_DAILY_LIMIT_CHAT": 3, "AI_DAILY_LIMIT_RECEIPT_SCAN": 2,
        "AI_DAILY_LIMIT_SUGGESTION": 2, "AI_DAILY_LIMIT_CATEGORIZE": 2, "AI_DAILY_LIMIT_NUDGE": 4,
        "AI_DAILY_LIMIT_PER_USER_TOTAL": 100, "AI_GLOBAL_DAILY_LIMIT": 1000, "AI_ALERT_THRESHOLD_PERCENT": 80,
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)


def usage_count(db_session, user, kind=None):
    query = db_session.query(AiUsageEvent).filter(AiUsageEvent.user_id == user.id)
    if kind:
        query = query.filter(AiUsageEvent.kind == kind.value)
    return query.count()


def chat(client, headers, message="مرحبا"):
    return client.post("/api/v1/agent/chat", headers=headers, json={"message": message})


# ------------------------------------------------------------------ المحادثة

def test_chat_over_daily_limit_returns_429_with_retry_after(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790100001")
    provider = FakeReplyProvider("أهلين")
    patch_provider(monkeypatch, provider)

    for _ in range(3):
        assert chat(client, headers).status_code == 200
    blocked = chat(client, headers)

    assert blocked.status_code == 429
    assert "للحد اليومي" in blocked.json()["detail"]
    assert int(blocked.headers["Retry-After"]) > 0
    assert len(provider.calls) == 3  # الاستدعاء المحظور ما وصل لـ Gemini أصلًا
    assert usage_count(db_session, user, AiUsageKind.CHAT) == 3
    # ورسالة المستخدم المحظورة ما انحفظت بالسجل (3 أسئلة + 3 ردود فقط)
    assert db_session.query(AgentInteraction).filter(AgentInteraction.user_id == user.id).count() == 6


def test_failed_ai_calls_do_not_consume_quota(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790100002")

    class Failing:
        def generate_reply(self, system_prompt, user_message, history=None):
            return AgentReply(text="مشغول", raw_error="503")

    patch_provider(monkeypatch, Failing())
    for _ in range(5):
        assert chat(client, headers).status_code == 200  # رسالة اعتذار، مش 429
    assert usage_count(db_session, user) == 0


def test_limit_zero_means_unlimited(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "AI_DAILY_LIMIT_CHAT", 0)
    headers, user = register_with_persona(client, db_session, "0790100003")
    patch_provider(monkeypatch, FakeReplyProvider("أهلين"))
    for _ in range(6):
        assert chat(client, headers).status_code == 200


def test_per_user_total_limit_applies_across_kinds(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "AI_DAILY_LIMIT_PER_USER_TOTAL", 2)
    headers, user = register_with_persona(client, db_session, "0790100004")
    patch_provider(monkeypatch, FakeReplyProvider("أهلين"))
    ai_usage_service.record_usage(db_session, user, AiUsageKind.RECEIPT_SCAN)
    assert chat(client, headers).status_code == 200
    assert chat(client, headers).status_code == 429


def test_global_limit_returns_503_for_everyone(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "AI_GLOBAL_DAILY_LIMIT", 2)
    headers_a, user_a = register_with_persona(client, db_session, "0790100005")
    headers_b, _ = register_with_persona(client, db_session, "0790100006")
    patch_provider(monkeypatch, FakeReplyProvider("أهلين"))
    assert chat(client, headers_a).status_code == 200
    assert chat(client, headers_a).status_code == 200
    blocked = chat(client, headers_b)  # مستخدم تاني ما استهلك شي، بس الحد العام انتهى
    assert blocked.status_code == 503
    assert "Retry-After" in blocked.headers


def test_demo_mode_disables_quotas(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "demo")
    headers, user = register_with_persona(client, db_session, "0790100007")
    patch_provider(monkeypatch, FakeReplyProvider("أهلين"))
    for _ in range(6):
        assert chat(client, headers).status_code == 200
    assert usage_count(db_session, user) == 0


# ------------------------------------------------------------- النافذة المتحركة

def test_window_is_rolling_24_hours(db_session, client):
    headers, user = register_with_persona(client, db_session, "0790100008")
    for hours_ago in (30, 26, 23):
        ai_usage_service.record_usage(db_session, user, AiUsageKind.CHAT, now=NOW - timedelta(hours=hours_ago))

    status_now = ai_usage_service.check_quota(db_session, user, AiUsageKind.CHAT, now=NOW)
    assert status_now.allowed  # حدثين فقط داخل النافذة (23 ساعة وأقل)، والحد 3

    ai_usage_service.record_usage(db_session, user, AiUsageKind.CHAT, now=NOW - timedelta(hours=1))
    ai_usage_service.record_usage(db_session, user, AiUsageKind.CHAT, now=NOW - timedelta(minutes=30))
    blocked = ai_usage_service.check_quota(db_session, user, AiUsageKind.CHAT, now=NOW)
    assert not blocked.allowed and blocked.reason == "user_kind"
    # الأقدم داخل النافذة منذ 23 ساعة → بينتهي المنع بعد ساعة تقريبًا
    assert 3500 <= blocked.retry_after_seconds <= 3700

    # بعد 25 ساعة من أول حدث بالنافذة، الحد بينفك
    later = NOW + timedelta(hours=2)
    assert ai_usage_service.check_quota(db_session, user, AiUsageKind.CHAT, now=later).allowed


def test_first_usage_of_the_day_prunes_events_older_than_a_week(db_session, client):
    headers, user = register_with_persona(client, db_session, "0790100009")
    db_session.add(AiUsageEvent(user_id=user.id, kind="chat", created_at=NOW - timedelta(days=9)))
    db_session.add(AiUsageEvent(user_id=user.id, kind="chat", created_at=NOW - timedelta(days=3)))
    db_session.commit()

    ai_usage_service.record_usage(db_session, user, AiUsageKind.CHAT, now=NOW)

    remaining = [e.created_at for e in db_session.query(AiUsageEvent).all()]
    assert len(remaining) == 2  # الحدث الأقدم من 7 أيام انحذف


# ----------------------------------------------------------------- التنبيهات

def test_alerts_fire_once_at_threshold_and_once_at_limit(client, db_session, monkeypatch, caplog):
    monkeypatch.setattr(settings, "AI_DAILY_LIMIT_CHAT", 5)  # 80% = 4
    headers, user = register_with_persona(client, db_session, "0790100010")

    with caplog.at_level(logging.WARNING, logger="rasheed.usage"):
        for _ in range(5):
            ai_usage_service.record_usage(db_session, user, AiUsageKind.CHAT)

    approaching = [r for r in caplog.records if "approaching" in r.getMessage() and "user_kind" in r.getMessage()]
    reached = [r for r in caplog.records if "REACHED" in r.getMessage() and "user_kind" in r.getMessage()]
    assert len(approaching) == 1 and len(reached) == 1
    assert "مرحبا" not in caplog.text  # السجلات ما فيها محتوى مستخدم


# ----------------------------------------------------------------- قراءة الفواتير

class FakeImageProvider:
    def __init__(self):
        self.calls = 0

    def analyze_image(self, system_prompt, user_message, image_bytes, mime_type):
        self.calls += 1
        return AgentReply(text='{"amount": 5, "category_id": null, "note": "x"}')

    def generate_reply(self, *args, **kwargs):
        raise NotImplementedError


def test_receipt_scan_limit(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790100011")
    provider = FakeImageProvider()
    monkeypatch.setattr(transactions_route, "get_ai_provider", lambda: provider)

    def scan():
        return client.post(
            "/api/v1/transactions/scan-receipt", headers=headers,
            files={"file": ("r.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        )

    assert scan().status_code == 200
    assert scan().status_code == 200
    blocked = scan()
    assert blocked.status_code == 429
    assert provider.calls == 2


# ----------------------------------------------------------------- التصنيف الذكي

class CountingProvider:
    def __init__(self):
        self.calls = 0

    def generate_reply(self, system_prompt, user_message, history=None):
        self.calls += 1
        return AgentReply(text="{}")


def test_quick_log_falls_back_to_rule_based_when_categorize_limit_is_reached(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790100012")
    db_session.add(Category(
        name="مطاعم", icon="utensils", is_default=True, category_type=CategoryType.EXPENSE, keywords=["مطعم"],
    ))
    db_session.commit()
    provider = CountingProvider()
    monkeypatch.setattr(categorizer_factory, "get_categorizer", lambda: GeminiCategorizer(provider))
    from app.services import transaction_service
    monkeypatch.setattr(transaction_service, "get_categorizer", lambda: GeminiCategorizer(provider))

    def quick_log():
        return client.post("/api/v1/transactions/quick-log", headers=headers, json={
            "amount": 3, "type": "expense", "note": "غدا بمطعم الحارة",
        })

    for _ in range(4):
        assert quick_log().status_code == 201  # التسجيل ما بيتوقف أبدًا
    assert provider.calls == 2  # بعد الحد (2) رجع للتصنيف بالكلمات المفتاحية بدون استدعاء Gemini
    assert usage_count(db_session, user, AiUsageKind.CATEGORIZE) == 2


# ----------------------------------------------------------------- اقتراحات التصنيف

class CountingJsonProvider:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def generate_reply(self, *args, **kwargs):
        self.calls += 1
        return AgentReply(text=self.text)


def add_uncategorized(db_session, user, count):
    for index in range(count):
        db_session.add(Transaction(
            user_id=user.id, amount=5 + index, type=TransactionType.EXPENSE, source=TransactionSource.MANUAL,
            note=f"معاملة {index}",
            occurred_at=datetime.now(timezone.utc),
        ))
    db_session.commit()


def test_suggestion_generation_stops_gracefully_at_limit(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "AI_DAILY_LIMIT_SUGGESTION", 1)
    headers, user = register_with_persona(client, db_session, "0790100013")
    db_session.add(Category(name="تسوق", icon="bag", is_default=True, category_type=CategoryType.EXPENSE, keywords=[]))
    db_session.commit()
    add_uncategorized(db_session, user, 3)
    category = db_session.query(Category).first()
    provider = CountingJsonProvider(f'{{"category_id": "{category.id}", "reasoning": "تسوق"}}')
    monkeypatch.setattr(agent_action_service, "get_ai_provider", lambda: provider)

    first = client.post("/api/v1/agent/actions/check", headers=headers)
    assert first.status_code == 200
    assert len(first.json()) == 1  # حد الاقتراحات 1: ولّد واحد وتوقف بدون خطأ
    assert provider.calls == 1

    second = client.post("/api/v1/agent/actions/check", headers=headers)
    assert second.status_code == 429  # من أول استدعاء والحد منتهي
    assert db_session.query(AgentAction).filter(AgentAction.user_id == user.id).count() == 1
