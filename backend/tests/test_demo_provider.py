"""
R12 — مزوّد الـ Demo: سيناريو العرض يكتمل بدون أي اتصال بـ Gemini.
"""
import json

import pytest

from app.agent import providers as providers_package  # noqa: F401
from app.agent.providers import factory as provider_factory
from app.agent.providers import gemini_provider
from app.agent.providers.demo_provider import DemoProvider
from app.config import settings
from app.models.agent import AgentAction, AgentActionStatus, AgentActionType
from app.models.category import Category, CategoryType
from app.models.ai_usage import AiUsageEvent
from app.services.categorizer import factory as categorizer_factory
from app.services.categorizer.rule_based import RuleBasedCategorizer
from tests.test_income_and_goal_delete import register_with_persona

NUDGE_TEXT = "بادر إنت بالحديث الآن — المستخدم ما كتب إلك شي"
CATEGORY_SYSTEM = "أنت مصنّف مصاريف دقيق. رد بصيغة JSON فقط، بدون أي نص إضافي."


@pytest.fixture(autouse=True)
def demo_mode(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "demo")
    provider_factory.get_ai_provider.cache_clear()
    categorizer_factory.get_categorizer.cache_clear()

    def no_network(*args, **kwargs):
        raise AssertionError("وضع الـ Demo ما لازم يلمس Gemini أبدًا")

    monkeypatch.setattr(gemini_provider.genai, "Client", no_network)
    yield
    provider_factory.get_ai_provider.cache_clear()
    categorizer_factory.get_categorizer.cache_clear()


def seed_categories(db_session):
    names = {"مطاعم وكافيهات": CategoryType.EXPENSE, "ترفيه": CategoryType.EXPENSE, "بقالة وسوبرماركت": CategoryType.EXPENSE}
    for name, kind in names.items():
        db_session.add(Category(name=name, icon="x", is_default=True, category_type=kind, keywords=[]))
    db_session.commit()
    return {c.name: str(c.id) for c in db_session.query(Category).all()}


def test_factories_return_demo_and_rule_based_without_touching_gemini():
    assert isinstance(provider_factory.get_ai_provider(), DemoProvider)
    assert isinstance(categorizer_factory.get_categorizer(), RuleBasedCategorizer)


def test_health_reports_the_ai_provider(client):
    assert client.get("/health").json()["ai_provider"] == "demo"


@pytest.mark.parametrize("message, expected_word", [
    ("مرحبا", "أهلين"),
    ("كم باقيلي عشان أوصل لهدفي؟", "مسار الهدف"),
    ("كيف كانت مصاريفي هالأسبوع؟", "مصاريفك"),
    ("اعطيني نصيحة أوفّر فيها اليوم", "التوفير"),
    ("شو الطقس اليوم", "العرض التجريبي"),
])
def test_scripted_chat_replies(message, expected_word):
    reply = DemoProvider().generate_reply("persona prompt", message)
    assert reply.raw_error is None
    assert expected_word in reply.text
    assert "<<<" not in reply.text


def test_nudge_tone_depends_on_mood():
    concerned = DemoProvider().generate_reply("حالتك المزاجية الحالية تجاهه: concerned", NUDGE_TEXT).text
    energized = DemoProvider().generate_reply("حالتك المزاجية الحالية تجاهه: energized", NUDGE_TEXT).text
    assert concerned != energized and concerned and energized


def test_arabic_digits_and_hamza_variants_are_understood():
    reply = DemoProvider().generate_reply("p", "أجاني ٢٥ دينار اليوم").text
    assert "<<<INCOME_LOG_PROPOSAL>>>" in reply and '"amount": 25.0' in reply


def test_income_report_through_chat_creates_a_pending_suggestion(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790110001")

    response = client.post("/api/v1/agent/chat", headers=headers, json={"message": "اجاني 25 دينار اليوم"})

    assert response.status_code == 200
    body = response.json()
    assert body["ai_available"] is True and "<<<" not in body["reply"]
    action = db_session.query(AgentAction).filter(AgentAction.user_id == user.id).one()
    assert action.action_type == AgentActionType.SUGGEST_INCOME_LOG
    assert action.status == AgentActionStatus.PENDING
    assert float(action.payload["amount"]) == 25.0

    confirmed = client.post(f"/api/v1/agent/actions/{action.id}/confirm", headers=headers)
    assert confirmed.status_code == 200
    transactions = client.get("/api/v1/transactions", headers=headers).json()
    assert [t["amount"] for t in transactions] == [25.0] and transactions[0]["type"] == "income"


def test_goal_phrase_through_chat_creates_goal_suggestion(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790110002")
    client.post("/api/v1/agent/chat", headers=headers, json={"message": "بدي اجمع 500 دينار للابتوب"})
    action = db_session.query(AgentAction).filter(AgentAction.user_id == user.id).one()
    assert action.action_type == AgentActionType.SUGGEST_GOAL_CREATION
    assert float(action.payload["target_amount"]) == 500.0


def test_category_json_picks_the_matching_category(db_session):
    ids = seed_categories(db_session)
    options = "\n".join(f"- {cid}: {name}" for name, cid in ids.items())
    message = f'المستخدم كتب وصف مصروف: "سهرة مع الشباب"\nاختر أنسب تصنيف من هالقائمة (id: اسم):\n{options}\n'

    parsed = json.loads(DemoProvider().generate_reply(CATEGORY_SYSTEM, message).text)

    assert parsed["category_id"] == ids["ترفيه"] and parsed["confidence"] > 0.5


def test_category_json_returns_null_when_nothing_matches(db_session):
    ids = seed_categories(db_session)
    options = "\n".join(f"- {cid}: {name}" for name, cid in ids.items())
    message = f'معاملة مالية بدون تصنيف، وصفها: "هدية لصاحبي"\n{options}\n'
    parsed = json.loads(DemoProvider().generate_reply(CATEGORY_SYSTEM, message).text)
    assert parsed["category_id"] is None


def test_receipt_scan_works_offline(client, db_session):
    ids = seed_categories(db_session)
    headers, _ = register_with_persona(client, db_session, "0790110003")

    response = client.post(
        "/api/v1/transactions/scan-receipt", headers=headers,
        files={"file": ("r.jpg", b"any-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["readable"] is True and body["amount"] == 12.5
    assert body["category_id"] == ids["بقالة وسوبرماركت"]


def test_suggestion_check_works_offline(client, db_session):
    from datetime import datetime, timezone

    from app.models.transaction import Transaction, TransactionSource, TransactionType

    ids = seed_categories(db_session)
    headers, user = register_with_persona(client, db_session, "0790110004")
    db_session.add(Transaction(
        user_id=user.id, amount=18, type=TransactionType.EXPENSE, source=TransactionSource.MANUAL,
        note="سهرة مع الشباب", occurred_at=datetime.now(timezone.utc),
    ))
    db_session.commit()

    response = client.post("/api/v1/agent/actions/check", headers=headers)

    assert response.status_code == 200
    suggestion = response.json()[0]
    assert suggestion["action_type"] == "suggest_category_correction"
    assert suggestion["payload"]["new_category_id"] == ids["ترفيه"]


def test_demo_mode_does_not_record_usage(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790110005")
    for _ in range(3):
        client.post("/api/v1/agent/chat", headers=headers, json={"message": "مرحبا"})
    assert db_session.query(AiUsageEvent).count() == 0
