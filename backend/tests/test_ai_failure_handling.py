"""
R06 — فشل الذكاء الاصطناعي بالمحادثة: رسالة مفهومة، بدون حفظ بسجل المحادثة، وإعادة المحاولة آمنة.
"""
from app.agent.providers.base import AgentReply
from app.models.agent import AgentAction, AgentInteraction
from tests.test_income_and_goal_delete import FakeReplyProvider, patch_provider, register_with_persona

APOLOGY = "خدمة الذكاء الاصطناعي مشغولة هلأ، جرب كمان شوي 🙏"


class FailingProvider:
    def generate_reply(self, system_prompt, user_message, history=None):
        return AgentReply(text=APOLOGY, raw_error="503 UNAVAILABLE high demand")


def test_failed_chat_returns_apology_flagged_and_not_persisted(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790090001")
    patch_provider(monkeypatch, FailingProvider())

    response = client.post("/api/v1/agent/chat", headers=headers, json={"message": "كم باقيلي؟"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == APOLOGY
    assert body["ai_available"] is False
    assert db_session.query(AgentInteraction).filter(AgentInteraction.user_id == user.id).count() == 0
    assert db_session.query(AgentAction).filter(AgentAction.user_id == user.id).count() == 0


def test_retry_after_failure_is_safe_and_history_stays_clean(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790090002")

    patch_provider(monkeypatch, FailingProvider())
    client.post("/api/v1/agent/chat", headers=headers, json={"message": "كم باقيلي؟"})

    good = FakeReplyProvider("باقيلك 90 دينار")
    patch_provider(monkeypatch, good)
    response = client.post("/api/v1/agent/chat", headers=headers, json={"message": "كم باقيلي؟"})

    assert response.status_code == 200
    assert response.json() == {"reply": "باقيلك 90 دينار", "ai_available": True}
    # سجل المحادثة فيه فقط الرسالة الناجحة (سؤال + رد)، بدون تكرار وبدون رسالة الاعتذار
    stored = db_session.query(AgentInteraction).filter(AgentInteraction.user_id == user.id).all()
    assert sorted(i.message for i in stored) == sorted(["كم باقيلي؟", "باقيلك 90 دينار"])
    history_sent_to_provider = good.calls[0][2]
    assert all(APOLOGY not in turn.text for turn in history_sent_to_provider)


def test_successful_chat_is_marked_available(client, db_session, monkeypatch):
    headers, _ = register_with_persona(client, db_session, "0790090003")
    patch_provider(monkeypatch, FakeReplyProvider("أهلين"))
    response = client.post("/api/v1/agent/chat", headers=headers, json={"message": "مرحبا"})
    assert response.json()["ai_available"] is True
