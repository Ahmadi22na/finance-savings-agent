"""
R13 — تجربة الشخصيات الثلاث وتقييمها: التبديل بحرية، بدون أي تأثير على الأرقام المالية، وتقييم مختصر بدون نص حر.
"""
import pytest

from app.agent.mood_engine import compute_mood_state
from app.models.persona import Persona
from app.models.persona_feedback import PersonaFeedback
from app.models.user import User
from app.services import usage_metrics_service
from tests.test_income_and_goal_delete import FakeReplyProvider, patch_provider

PASSWORD = "testpassword123"
PERSONA_KEYS = ("wise", "business", "energetic")


def seed_personas(db_session):
    personas = {}
    for key in PERSONA_KEYS:
        persona = Persona(
            key=key, display_name=f"رشيد {key}", tagline="t", color_hex="#000000",
            system_prompt=f"PERSONA-MARKER-{key}", is_active=True,
        )
        db_session.add(persona)
        personas[key] = persona
    db_session.commit()
    return personas


def onboarded_user(client, db_session, phone, persona):
    token = client.post("/api/v1/auth/register", json={
        "name": "مستخدم تجربة", "phone": phone, "password": PASSWORD,
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/onboarding/complete", headers=headers, json={"persona_id": str(persona.id)})
    user = db_session.query(User).filter(User.phone == phone).one()
    return headers, user


def switch(client, headers, persona):
    return client.patch("/api/v1/users/me/persona", headers=headers, json={"persona_id": str(persona.id)})


def rate(client, headers, persona, rating, tags=None):
    body = {"persona_id": str(persona.id), "rating": rating}
    if tags is not None:
        body["tags"] = tags
    return client.put("/api/v1/users/me/persona-feedback", headers=headers, json=body)


# ------------------------------------------------------------------- التبديل

def test_user_can_try_each_persona_and_chat_uses_the_selected_one(client, db_session, monkeypatch):
    personas = seed_personas(db_session)
    headers, _ = onboarded_user(client, db_session, "0790180001", personas["wise"])
    provider = FakeReplyProvider("تمام")
    patch_provider(monkeypatch, provider)

    for key in PERSONA_KEYS:
        response = switch(client, headers, personas[key])
        assert response.status_code == 200 and response.json()["persona"]["key"] == key
        assert client.post("/api/v1/agent/chat", headers=headers, json={"message": "مرحبا"}).status_code == 200
        assert f"PERSONA-MARKER-{key}" in provider.calls[-1][0]  # System Prompt الشخصية الجديدة فعلًا

    assert client.get("/api/v1/users/me", headers=headers).json()["persona"]["key"] == "energetic"


def test_switching_persona_never_changes_financial_data(client, db_session):
    personas = seed_personas(db_session)
    headers, user = onboarded_user(client, db_session, "0790180002", personas["wise"])
    goal = client.post("/api/v1/goals", headers=headers, json={"title": "لابتوب جديد", "target_amount": 600}).json()
    income = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 100, "type": "income", "note": "دخل",
    }).json()
    client.post("/api/v1/transactions/quick-log", headers=headers, json={"amount": 12, "type": "expense", "note": "غدا"})
    client.post(f"/api/v1/transactions/{income['id']}/allocate", headers=headers, json={
        "allocations": [{"goal_id": goal["id"], "amount": 40}],
    })

    def snapshot():
        db_session.expire_all()
        refreshed = db_session.query(User).filter(User.id == user.id).one()
        mood = compute_mood_state(db_session, refreshed)
        return (
            client.get("/api/v1/goals", headers=headers).json(),
            client.get("/api/v1/transactions", headers=headers).json(),
            (mood.state, mood.reason),
        )

    before = snapshot()
    for key in ("business", "energetic", "wise"):
        assert switch(client, headers, personas[key]).status_code == 200
    assert snapshot() == before


def test_switching_to_unknown_or_inactive_persona_is_rejected_and_keeps_the_current_one(client, db_session):
    personas = seed_personas(db_session)
    headers, _ = onboarded_user(client, db_session, "0790180003", personas["wise"])
    personas["business"].is_active = False
    db_session.commit()

    inactive = switch(client, headers, personas["business"])
    unknown = client.patch("/api/v1/users/me/persona", headers=headers, json={
        "persona_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    })

    assert inactive.status_code == 404 and unknown.status_code == 404
    assert client.get("/api/v1/users/me", headers=headers).json()["persona"]["key"] == "wise"


def test_persona_endpoints_need_authentication(client, db_session):
    personas = seed_personas(db_session)
    body = {"persona_id": str(personas["wise"].id)}
    assert client.patch("/api/v1/users/me/persona", json=body).status_code == 401
    assert client.put("/api/v1/users/me/persona-feedback", json={**body, "rating": 5}).status_code == 401
    assert client.get("/api/v1/users/me/persona-feedback").status_code == 401


# ------------------------------------------------------------------- التقييم

def test_rating_is_saved_and_rerating_updates_the_same_row(client, db_session):
    personas = seed_personas(db_session)
    headers, user = onboarded_user(client, db_session, "0790180004", personas["wise"])

    first = rate(client, headers, personas["wise"], 3, ["too_long"])
    second = rate(client, headers, personas["wise"], 5, ["friendly", "helpful", "friendly"])

    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["rating"] == 5 and second.json()["tags"] == ["friendly", "helpful"]  # مرتّبة وبدون تكرار
    assert db_session.query(PersonaFeedback).filter(PersonaFeedback.user_id == user.id).count() == 1
    mine = client.get("/api/v1/users/me/persona-feedback", headers=headers).json()
    assert len(mine) == 1 and mine[0]["persona_id"] == str(personas["wise"].id)


@pytest.mark.parametrize("body", [
    {"rating": 0}, {"rating": 6}, {"rating": 3, "tags": ["free text"]}, {"rating": 3, "tags": ["helpful"] * 7},
])
def test_invalid_ratings_are_rejected(client, db_session, body):
    personas = seed_personas(db_session)
    headers, user = onboarded_user(client, db_session, "0790180005", personas["wise"])

    response = client.put("/api/v1/users/me/persona-feedback", headers=headers, json={
        "persona_id": str(personas["wise"].id), **body,
    })

    assert response.status_code == 422
    assert db_session.query(PersonaFeedback).filter(PersonaFeedback.user_id == user.id).count() == 0


def test_rating_an_unknown_persona_is_404(client, db_session):
    personas = seed_personas(db_session)
    headers, _ = onboarded_user(client, db_session, "0790180006", personas["wise"])
    response = client.put("/api/v1/users/me/persona-feedback", headers=headers, json={
        "persona_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "rating": 4,
    })
    assert response.status_code == 404


def test_feedback_is_private_to_each_user(client, db_session):
    personas = seed_personas(db_session)
    headers_a, _ = onboarded_user(client, db_session, "0790180007", personas["wise"])
    headers_b, _ = onboarded_user(client, db_session, "0790180008", personas["wise"])
    rate(client, headers_a, personas["wise"], 5)

    assert len(client.get("/api/v1/users/me/persona-feedback", headers=headers_a).json()) == 1
    assert client.get("/api/v1/users/me/persona-feedback", headers=headers_b).json() == []


def test_user_can_rate_all_three_personas_independently(client, db_session):
    personas = seed_personas(db_session)
    headers, _ = onboarded_user(client, db_session, "0790180009", personas["wise"])
    for key, stars in zip(PERSONA_KEYS, (5, 3, 4)):
        assert rate(client, headers, personas[key], stars).status_code == 200
    ratings = {item["persona_id"]: item["rating"] for item in client.get(
        "/api/v1/users/me/persona-feedback", headers=headers).json()}
    assert ratings == {str(personas["wise"].id): 5, str(personas["business"].id): 3, str(personas["energetic"].id): 4}


# ---------------------------------------------------------- التقرير وحذف الحساب

def test_report_compares_personas_without_personal_data(client, db_session):
    personas = seed_personas(db_session)
    headers_a, _ = onboarded_user(client, db_session, "0790180010", personas["wise"])
    headers_b, _ = onboarded_user(client, db_session, "0790180011", personas["wise"])
    rate(client, headers_a, personas["wise"], 5, ["friendly", "helpful"])
    rate(client, headers_b, personas["wise"], 2, ["too_long"])
    rate(client, headers_a, personas["business"], 4, ["friendly"])

    report = usage_metrics_service.build_report(db_session)
    by_key = {item["key"]: item for item in report["personas"]}

    assert by_key["wise"]["users_now"] == 2 and by_key["wise"]["ratings"] == 2
    assert by_key["wise"]["avg_rating"] == 3.5 and by_key["wise"]["positive_percent"] == 50.0
    assert by_key["business"]["ratings"] == 1 and by_key["energetic"]["ratings"] == 0
    assert ("friendly", 1) in by_key["wise"]["top_tags"]
    markdown = usage_metrics_service.render_markdown(report)
    assert "## 6. مقارنة شخصيات رشيد" in markdown and "مستخدم تجربة" not in markdown and "07901800" not in markdown


def test_feedback_is_deleted_with_the_account(client, db_session):
    personas = seed_personas(db_session)
    headers, user = onboarded_user(client, db_session, "0790180012", personas["wise"])
    rate(client, headers, personas["wise"], 4)

    deleted = client.request("DELETE", "/api/v1/users/me", headers=headers, json={"password": PASSWORD, "confirm": True})

    assert deleted.status_code == 204
    assert db_session.query(PersonaFeedback).filter(PersonaFeedback.user_id == user.id).count() == 0
