"""
R09 — الـ Onboarding السريع: كل شي اختياري، والمستخدم بيوصل لأول معاملة/هدف بدون تعبئة معلومات غير لازمة.
"""
import pytest

from app.models.goal import Goal
from app.models.persona import Persona
from app.models.user import User
from tests.test_income_and_goal_delete import FakeReplyProvider, patch_provider

PASSWORD = "testpassword123"


def seed_personas(db_session, *keys):
    created = {}
    for key in keys:
        persona = Persona(
            key=key, display_name=f"رشيد {key}", tagline="t", color_hex="#000000", system_prompt="كن لطيفًا.", is_active=True,
        )
        db_session.add(persona)
        created[key] = persona
    db_session.commit()
    return created


def new_user(client, phone):
    """مستخدم مسجّل جديد بدون ما يكون خلّص الـ Onboarding."""
    token = client.post("/api/v1/auth/register", json={
        "name": "مستخدم جديد", "phone": phone, "password": PASSWORD,
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def complete(client, headers, **body):
    return client.post("/api/v1/onboarding/complete", headers=headers, json=body)


def user_row(db_session, phone):
    db_session.expire_all()
    return db_session.query(User).filter(User.phone == phone).one()


def test_minimal_onboarding_with_an_empty_request(client, db_session):
    personas = seed_personas(db_session, "wise", "energetic")
    headers = new_user(client, "0790170001")

    response = complete(client, headers)

    assert response.status_code == 200
    body = response.json()
    assert body["has_completed_onboarding"] is True
    assert body["income_type"] == "variable"
    assert body["persona"]["key"] == "energetic"  # الشخصية الافتراضية
    assert body["persona"]["id"] == str(personas["energetic"].id)
    assert db_session.query(Goal).count() == 0  # ما انخلق هدف بالغصب


def test_full_onboarding_still_works_and_creates_the_goal(client, db_session):
    personas = seed_personas(db_session, "wise", "energetic")
    headers = new_user(client, "0790170002")

    response = complete(
        client, headers, income_type="fixed", persona_id=str(personas["wise"].id),
        goal_title="صندوق الطوارئ", goal_target_amount=1000, goal_deadline="2027-06-30",
    )

    assert response.status_code == 200
    assert response.json()["persona"]["key"] == "wise" and response.json()["income_type"] == "fixed"
    goal = db_session.query(Goal).one()
    assert goal.title == "صندوق الطوارئ" and float(goal.target_amount) == 1000.0 and str(goal.deadline) == "2027-06-30"


@pytest.mark.parametrize("body", [
    {"goal_title": "سفر"},                          # عنوان بدون مبلغ
    {"goal_target_amount": 500},                    # مبلغ بدون عنوان
    {"goal_deadline": "2027-01-01"},                # موعد بدون هدف
    {"goal_title": "سفر", "goal_target_amount": 0},  # مبلغ صفر
    {"goal_title": "س", "goal_target_amount": 10},  # عنوان قصير
])
def test_half_filled_goal_is_rejected_and_nothing_changes(client, db_session, body):
    seed_personas(db_session, "energetic")
    headers = new_user(client, "0790170003")

    assert complete(client, headers, **body).status_code == 422

    assert user_row(db_session, "0790170003").has_completed_onboarding is False
    assert db_session.query(Goal).count() == 0


def test_default_persona_falls_back_to_the_first_active_one(client, db_session):
    seed_personas(db_session, "wise", "business")  # بدون energetic (الافتراضية)
    headers = new_user(client, "0790170004")
    assert complete(client, headers).json()["persona"]["key"] == "wise"


def test_inactive_default_persona_is_skipped(client, db_session):
    personas = seed_personas(db_session, "energetic", "wise")
    personas["energetic"].is_active = False
    db_session.commit()
    headers = new_user(client, "0790170005")
    assert complete(client, headers).json()["persona"]["key"] == "wise"


def test_no_personas_at_all_gives_a_clear_error(client, db_session):
    headers = new_user(client, "0790170006")
    response = complete(client, headers)
    assert response.status_code == 400
    assert user_row(db_session, "0790170006").has_completed_onboarding is False


def test_unknown_persona_is_still_404_and_onboarding_runs_only_once(client, db_session):
    seed_personas(db_session, "energetic")
    headers = new_user(client, "0790170007")

    assert complete(client, headers, persona_id="3fa85f64-5717-4562-b3fc-2c963f66afa6").status_code == 404
    assert complete(client, headers).status_code == 200
    assert complete(client, headers).status_code == 400  # ما بتنعاد


def test_after_the_fast_path_the_user_reaches_core_value_immediately(client, db_session, monkeypatch):
    """سيناريو القيمة الأساسية: Onboarding بدون أي إدخال ← أول معاملة ← أول هدف ← محادثة مع رشيد."""
    seed_personas(db_session, "energetic")
    headers = new_user(client, "0790170008")
    assert complete(client, headers).status_code == 200

    transaction = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 4.5, "type": "expense", "note": "قهوة",
    })
    goal = client.post("/api/v1/goals", headers=headers, json={"title": "رحلة العقبة", "target_amount": 250})
    patch_provider(monkeypatch, FakeReplyProvider("أهلين فيك!"))
    chat = client.post("/api/v1/agent/chat", headers=headers, json={"message": "مرحبا"})

    assert transaction.status_code == 201 and goal.status_code == 201
    assert chat.status_code == 200 and chat.json()["reply"] == "أهلين فيك!"
    assert client.get("/api/v1/users/me", headers=headers).json()["has_completed_onboarding"] is True


def test_goal_can_be_added_later_without_having_one_at_onboarding(client, db_session):
    seed_personas(db_session, "energetic")
    headers = new_user(client, "0790170009")
    complete(client, headers)

    assert client.get("/api/v1/goals", headers=headers).json() == []
    assert client.post("/api/v1/goals", headers=headers, json={"title": "لابتوب", "target_amount": 600}).status_code == 201
