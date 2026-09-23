"""اختبارات: تسجيل الدخل عبر المحادثة، وحذف الأهداف."""
import pytest

from app.agent.providers.base import AgentReply
from app.agent.providers import factory as provider_factory
from app.models.persona import Persona
from app.services import agent_chat_service, agent_action_service


class FakeReplyProvider:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def generate_reply(self, system_prompt, user_message, history=None):
        self.calls.append((system_prompt, user_message, history))
        return AgentReply(text=self.text)


def patch_provider(monkeypatch, fake):
    monkeypatch.setattr(provider_factory, "get_ai_provider", lambda: fake)
    monkeypatch.setattr(agent_chat_service, "get_ai_provider", lambda: fake)


def register_with_persona(client, db_session, phone):
    persona = Persona(
        key="wise", display_name="رشيد الحكيم", tagline="خبرة",
        color_hex="#1B4332", system_prompt="كن حكيمًا.", is_active=True,
    )
    db_session.add(persona)
    db_session.commit()

    reg = client.post("/api/v1/auth/register", json={
        "name": "مستخدم اختبار", "phone": phone, "password": "testpassword123",
    }).json()
    headers = {"Authorization": f"Bearer {reg['access_token']}"}

    client.post("/api/v1/onboarding/complete", headers=headers, json={
        "income_type": "variable", "persona_id": str(persona.id),
        "goal_title": "هدف قديم", "goal_target_amount": 500,
    })
    from app.models.user import User
    user = db_session.query(User).filter(User.phone == phone).first()
    return headers, user


# ---------- تسجيل الدخل عبر المحادثة ----------

def test_income_log_marker_creates_pending_action(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790010001")
    reply_text = (
        'حلو! سجلتلك ياها. '
        '<<<INCOME_LOG_PROPOSAL>>>{"amount": 25, "note": "شغل يوم"}<<<END>>>'
    )
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    response = client.post("/api/v1/agent/chat", headers=headers, json={
        "message": "اشتغلت اليوم واجاني 25 دينار",
    })
    assert response.status_code == 200
    assert "INCOME_LOG_PROPOSAL" not in response.json()["reply"]

    pending = agent_action_service.list_pending_actions(db_session, user)
    income_actions = [a for a in pending if a.action_type.value == "suggest_income_log"]
    assert len(income_actions) == 1
    assert income_actions[0].payload["amount"] == 25


def test_confirming_income_log_creates_real_income_transaction(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790010002")
    reply_text = '<<<INCOME_LOG_PROPOSAL>>>{"amount": 25, "note": "شغل يوم"}<<<END>>>'
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    client.post("/api/v1/agent/chat", headers=headers, json={"message": "اجاني 25 دينار"})

    pending = agent_action_service.list_pending_actions(db_session, user)
    action_id = str(pending[0].id)

    confirm_response = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers)
    assert confirm_response.status_code == 200

    transactions_response = client.get("/api/v1/transactions", headers=headers)
    incomes = [t for t in transactions_response.json() if t["type"] == "income"]
    assert any(t["amount"] == 25 for t in incomes)


def test_income_report_does_not_trigger_goal_creation(client, db_session, monkeypatch):
    """
    محاكاة الـ Bug الفعلي يلي انلقط: مزود وهمي "مطيع" بيتبع التعليمات الصح
    (ما يستخدم GOAL_PROPOSAL لخبر دخل) — هاد اختبار توثيقي للسلوك المتوقع،
    مش ضمان سلوك Gemini الفعلي (هاد تحكمه صياغة الـ Prompt، مش الكود).
    """
    headers, user = register_with_persona(client, db_session, "0790010003")
    reply_text = '<<<INCOME_LOG_PROPOSAL>>>{"amount": 25, "note": "شغل يوم"}<<<END>>>'
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    client.post("/api/v1/agent/chat", headers=headers, json={"message": "اجاني 25 دينار"})

    pending = agent_action_service.list_pending_actions(db_session, user)
    goal_proposals = [a for a in pending if a.action_type.value == "suggest_goal_creation"]
    assert len(goal_proposals) == 0


# ---------- حذف هدف ----------

def test_delete_goal(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010004")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "هدف للحذف", "target_amount": 100,
    }).json()

    delete_response = client.delete(f"/api/v1/goals/{goal['id']}", headers=headers)
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/goals", headers=headers)
    remaining_ids = [g["id"] for g in list_response.json()]
    assert goal["id"] not in remaining_ids


def test_delete_nonexistent_goal_returns_404(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010005")
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.delete(f"/api/v1/goals/{fake_id}", headers=headers)
    assert response.status_code == 404


def test_cannot_delete_another_users_goal(client, db_session):
    headers1, user1 = register_with_persona(client, db_session, "0790010006")
    headers2, user2 = register_with_persona(client, db_session, "0790010007")

    goal = client.post("/api/v1/goals", headers=headers1, json={
        "title": "هدف خاص", "target_amount": 100,
    }).json()

    response = client.delete(f"/api/v1/goals/{goal['id']}", headers=headers2)
    assert response.status_code == 404
