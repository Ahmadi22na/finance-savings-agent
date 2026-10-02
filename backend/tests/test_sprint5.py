"""Module documentation."""
import pytest

from app.agent.providers.base import AgentReply
from app.agent.providers import factory as provider_factory
from app.models.persona import Persona
from app.services import agent_chat_service, agent_action_service


class FakeReplyProvider:
    """Fakereplyprovider documentation."""
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




def test_essentials_update_marker_saves_to_profile(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790009001")
    fake = FakeReplyProvider(
        'تمام، سجّلتها. <<<ESSENTIALS_UPDATE>>>{"monthly_estimate": 150}<<<END>>>'
    )
    patch_provider(monkeypatch, fake)

    response = client.post("/api/v1/agent/chat", headers=headers, json={
        "message": "بصرف حوالي 150 دينار شهريًا على الأكل والمواصلات",
    })
    assert response.status_code == 200
    assert "ESSENTIALS_UPDATE" not in response.json()["reply"]

    db_session.refresh(user)
    assert float(user.estimated_monthly_essentials) == 150


def test_essentials_estimate_from_profile_included_in_prompt(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790009002")
    user.estimated_monthly_essentials = 200
    db_session.commit()

    fake = FakeReplyProvider("تمام")
    patch_provider(monkeypatch, fake)

    client.post("/api/v1/agent/chat", headers=headers, json={"message": "شو رأيك بهدفي؟"})

    system_prompt_used = fake.calls[0][0]
    assert "200" in system_prompt_used




def test_goal_proposal_marker_creates_pending_action(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790009003")
    reply_text = (
        'جهزتلك اقتراح هدف بناءً على يلي حكيته! '
        '<<<GOAL_PROPOSAL>>>{"title": "مصاريف الشتا", "target_amount": 290, '
        '"breakdown": [{"label": "ملابس شتوية", "amount": 200}, {"label": "حلاقة", "amount": 30}, '
        '{"label": "جيم", "amount": 60}]}<<<END>>>'
    )
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    response = client.post("/api/v1/agent/chat", headers=headers, json={
        "message": "بدي 200 دينار ملابس شتوية وراح احلق كم مرة 30 دينار واشتراك جيم 60 دينار",
    })
    assert response.status_code == 200
    assert "GOAL_PROPOSAL" not in response.json()["reply"]

    pending = agent_action_service.list_pending_actions(db_session, user)
    goal_proposals = [a for a in pending if a.action_type.value == "suggest_goal_creation"]
    assert len(goal_proposals) == 1
    assert goal_proposals[0].payload["target_amount"] == 290


def test_confirming_goal_proposal_creates_real_goal(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790009004")
    reply_text = (
        'جهزتلك اقتراح! <<<GOAL_PROPOSAL>>>{"title": "مصاريف الشتا", "target_amount": 290, '
        '"breakdown": []}<<<END>>>'
    )
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    client.post("/api/v1/agent/chat", headers=headers, json={"message": "..."})

    pending = agent_action_service.list_pending_actions(db_session, user)
    action_id = str(pending[0].id)

    confirm_response = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers)
    assert confirm_response.status_code == 200

    from app.models.goal import Goal
    new_goal = db_session.query(Goal).filter(Goal.title == "مصاريف الشتا").first()
    assert new_goal is not None
    assert float(new_goal.target_amount) == 290


def test_malformed_protocol_block_is_stripped_and_ignored(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790009005")
    fake = FakeReplyProvider('نص عادي <<<GOAL_PROPOSAL>>>{بيانات غير صالحة<<<END>>> باقي الرد')
    patch_provider(monkeypatch, fake)

    response = client.post("/api/v1/agent/chat", headers=headers, json={"message": "..."})
    assert response.status_code == 200
    assert "GOAL_PROPOSAL" not in response.json()["reply"]

    pending = agent_action_service.list_pending_actions(db_session, user)
    assert len(pending) == 0


def test_normal_chat_without_markers_unaffected(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790009006")
    fake = FakeReplyProvider("أهلا فيك، شو بقدر أساعدك فيه اليوم؟")
    patch_provider(monkeypatch, fake)

    response = client.post("/api/v1/agent/chat", headers=headers, json={"message": "مرحبا"})
    assert response.status_code == 200
    assert response.json()["reply"] == "أهلا فيك، شو بقدر أساعدك فيه اليوم؟"
