"""اختبارات Sprint 2: الشخصيات (Personas)، الـ Onboarding، ومحرك الحالة المزاجية."""
import pytest
from datetime import datetime, timedelta, timezone

from app.models.persona import Persona
from app.models.transaction import Transaction, TransactionType, TransactionSource
from app.models.goal import Goal, GoalStatus
from app.agent.mood_engine import compute_mood_state, MoodState


@pytest.fixture(autouse=True)
def seed_personas(db_session):
    wise = Persona(
        key="wise", display_name="رشيد الحكيم", tagline="خبرة حياة",
        color_hex="#1B4332", system_prompt="كن حكيمًا وهادئًا.", is_active=True,
    )
    inactive = Persona(
        key="retired", display_name="شخصية قديمة", tagline="متوقفة",
        color_hex="#000000", system_prompt="غير مستخدمة", is_active=False,
    )
    db_session.add_all([wise, inactive])
    db_session.commit()


def register(client, phone="0790005555"):
    return client.post("/api/v1/auth/register", json={
        "name": "مستخدم اختبار", "phone": phone, "password": "testpassword123",
    }).json()


def get_wise_persona_id(client):
    personas = client.get("/api/v1/personas").json()
    return next(p["id"] for p in personas if p["key"] == "wise")


# ---------- Personas ----------

def test_list_personas_returns_only_active(client):
    response = client.get("/api/v1/personas")
    assert response.status_code == 200
    keys = [p["key"] for p in response.json()]
    assert "wise" in keys
    assert "retired" not in keys  # الشخصية غير المفعّلة ما لازم تظهر


def test_persona_response_never_leaks_system_prompt(client):
    response = client.get("/api/v1/personas")
    for persona in response.json():
        assert "system_prompt" not in persona


def test_personas_endpoint_requires_no_auth(client):
    """شاشة اختيار الشخصية تظهر أثناء الـ Onboarding — قبل ما نحتاج توكن."""
    response = client.get("/api/v1/personas")
    assert response.status_code == 200


# ---------- Onboarding ----------

def test_complete_onboarding_updates_user_and_creates_goal(client):
    reg = register(client)
    token = reg["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    persona_id = get_wise_persona_id(client)

    response = client.post("/api/v1/onboarding/complete", headers=headers, json={
        "income_type": "variable",
        "persona_id": persona_id,
        "goal_title": "رحلة سفر",
        "goal_target_amount": 1000,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["has_completed_onboarding"] is True
    assert data["persona"]["key"] == "wise"

    goals = client.get("/api/v1/goals", headers=headers).json()
    assert len(goals) == 1
    assert goals[0]["title"] == "رحلة سفر"


def test_onboarding_cannot_run_twice(client):
    reg = register(client)
    headers = {"Authorization": f"Bearer {reg['access_token']}"}
    persona_id = get_wise_persona_id(client)
    payload = {
        "income_type": "variable", "persona_id": persona_id,
        "goal_title": "هدف", "goal_target_amount": 500,
    }
    client.post("/api/v1/onboarding/complete", headers=headers, json=payload)
    response = client.post("/api/v1/onboarding/complete", headers=headers, json=payload)
    assert response.status_code == 400


def test_onboarding_rejects_inactive_persona(client, db_session):
    reg = register(client)
    headers = {"Authorization": f"Bearer {reg['access_token']}"}
    inactive_id = str(
        db_session.query(Persona).filter(Persona.key == "retired").first().id
    )
    response = client.post("/api/v1/onboarding/complete", headers=headers, json={
        "income_type": "variable", "persona_id": inactive_id,
        "goal_title": "هدف", "goal_target_amount": 500,
    })
    assert response.status_code == 404


def test_new_user_defaults_to_onboarding_not_completed(client):
    reg = register(client)
    assert reg["user"]["has_completed_onboarding"] is False
    assert reg["user"]["persona"] is None


# ---------- Mood Engine ----------

def _make_user(client, db_session, phone):
    reg = register(client, phone=phone)
    from app.models.user import User
    return db_session.query(User).filter(User.phone == phone).first()


def test_mood_neutral_by_default(client, db_session):
    user = _make_user(client, db_session, "0790006001")
    result = compute_mood_state(db_session, user)
    assert result.state == MoodState.NEUTRAL


def test_mood_energized_when_close_to_goal(client, db_session):
    user = _make_user(client, db_session, "0790006002")
    goal = Goal(user_id=user.id, title="هدف", target_amount=100, current_amount=90, status=GoalStatus.ACTIVE)
    db_session.add(goal)
    db_session.commit()

    result = compute_mood_state(db_session, user)
    assert result.state == MoodState.ENERGIZED


def test_mood_concerned_when_overspending(client, db_session):
    user = _make_user(client, db_session, "0790006003")
    now = datetime.now(timezone.utc)

    # معدل معتاد منخفض جدًا بالشهر الماضي (خارج نافذة الأسبوع الأخير)
    db_session.add(Transaction(
        user_id=user.id, amount=10, type=TransactionType.EXPENSE,
        source=TransactionSource.MANUAL, occurred_at=now - timedelta(days=20),
    ))
    # صرف كبير جدًا بالأسبوع الأخير
    db_session.add(Transaction(
        user_id=user.id, amount=500, type=TransactionType.EXPENSE,
        source=TransactionSource.MANUAL, occurred_at=now - timedelta(days=1),
    ))
    db_session.commit()

    result = compute_mood_state(db_session, user)
    assert result.state == MoodState.CONCERNED
