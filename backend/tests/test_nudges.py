"""اختبارات منطق الـ Nudges الاستباقية — بدون استدعاء Gemini الحقيقي (Fake Provider)."""
import pytest
from datetime import datetime, timedelta, timezone

from app.agent.providers.base import AgentReply
from app.agent.providers import factory as provider_factory
from app.models.persona import Persona
from app.models.goal import Goal, GoalStatus
from app.models.agent import AgentInteraction, InteractionTrigger
from app.services import nudge_service


class FakeProvider:
    """مزود وهمي يرجّع رد ثابت بدون أي اتصال شبكة فعلي — يخلي الاختبارات سريعة وموثوقة."""
    def __init__(self, text="رسالة تجريبية من رشيد", raw_error=None):
        self.text = text
        self.raw_error = raw_error
        self.calls = []

    def generate_reply(self, system_prompt, user_message):
        self.calls.append((system_prompt, user_message))
        return AgentReply(text=self.text, raw_error=self.raw_error)


@pytest.fixture
def fake_provider(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(provider_factory, "get_ai_provider", lambda: provider)
    monkeypatch.setattr(nudge_service, "get_ai_provider", lambda: provider)
    return provider


def register_with_persona(client, db_session, phone="0790007001"):
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
        "goal_title": "هدف", "goal_target_amount": 1000,
    })
    from app.models.user import User
    user = db_session.query(User).filter(User.phone == phone).first()
    return headers, user


def test_no_nudge_when_mood_is_neutral(client, db_session, fake_provider):
    headers, user = register_with_persona(client, db_session, "0790007001")
    response = client.get("/api/v1/agent/nudge", headers=headers)
    assert response.status_code == 200
    assert response.json()["nudge"] is None
    assert len(fake_provider.calls) == 0  # ما لازم نستدعي الـ AI أصلاً لو الحالة طبيعية


def test_nudge_generated_when_energized(client, db_session, fake_provider):
    headers, user = register_with_persona(client, db_session, "0790007002")
    goal = db_session.query(Goal).filter(Goal.user_id == user.id).first()
    goal.current_amount = 900  # قريب جدًا من هدفه (target=1000)
    db_session.commit()

    response = client.get("/api/v1/agent/nudge", headers=headers)
    assert response.status_code == 200
    assert response.json()["nudge"] == "رسالة تجريبية من رشيد"
    assert len(fake_provider.calls) == 1


def test_nudge_respects_cooldown(client, db_session, fake_provider):
    headers, user = register_with_persona(client, db_session, "0790007003")
    goal = db_session.query(Goal).filter(Goal.user_id == user.id).first()
    goal.current_amount = 900
    db_session.commit()

    first = client.get("/api/v1/agent/nudge", headers=headers)
    assert first.json()["nudge"] is not None

    # نفس اللحظة تقريبًا — لازم يرجع None لأننا لسا بفترة الـ Cooldown
    second = client.get("/api/v1/agent/nudge", headers=headers)
    assert second.json()["nudge"] is None
    assert len(fake_provider.calls) == 1  # ما استدعينا الـ AI مرة ثانية


def test_nudge_allowed_again_after_cooldown_expires(client, db_session, fake_provider):
    headers, user = register_with_persona(client, db_session, "0790007004")
    goal = db_session.query(Goal).filter(Goal.user_id == user.id).first()
    goal.current_amount = 900
    db_session.commit()

    # نزرع Nudge قديم يدويًا (قبل 13 ساعة) بدل ما ننتظر فعليًا بالاختبار
    old_nudge = AgentInteraction(
        user_id=user.id, trigger_type=InteractionTrigger.NUDGE,
        message="نودج قديم", is_from_user=False,
        created_at=datetime.now(timezone.utc) - timedelta(hours=13),
    )
    db_session.add(old_nudge)
    db_session.commit()

    response = client.get("/api/v1/agent/nudge", headers=headers)
    assert response.json()["nudge"] is not None


def test_no_nudge_before_onboarding_completed(client, db_session, fake_provider):
    reg = client.post("/api/v1/auth/register", json={
        "name": "مستخدم بدون onboarding", "phone": "0790007005", "password": "testpassword123",
    }).json()
    headers = {"Authorization": f"Bearer {reg['access_token']}"}

    response = client.get("/api/v1/agent/nudge", headers=headers)
    assert response.status_code == 200
    assert response.json()["nudge"] is None
    assert len(fake_provider.calls) == 0
