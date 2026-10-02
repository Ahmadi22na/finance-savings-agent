"""Module documentation."""
import pytest
from datetime import datetime, timezone

from app.agent.providers.base import AgentReply
from app.agent.providers import factory as provider_factory
from app.models.persona import Persona
from app.models.category import Category, CategoryType
from app.models.transaction import Transaction, TransactionType, TransactionSource
from app.models.goal import Goal
from app.services import agent_action_service


class FakeJsonProvider:
    """Fakejsonprovider documentation."""
    def __init__(self, json_text):
        self.json_text = json_text
        self.calls = []

    def generate_reply(self, system_prompt, user_message):
        self.calls.append((system_prompt, user_message))
        return AgentReply(text=self.json_text)


def patch_provider(monkeypatch, fake):
    monkeypatch.setattr(provider_factory, "get_ai_provider", lambda: fake)
    monkeypatch.setattr(agent_action_service, "get_ai_provider", lambda: fake)


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
        "goal_title": "هدف", "goal_target_amount": 1000,
    })
    from app.models.user import User
    user = db_session.query(User).filter(User.phone == phone).first()
    return headers, user


def add_uncategorized_transaction(db_session, user, note="سهرة مع الشباب"):
    transaction = Transaction(
        user_id=user.id, amount=5, type=TransactionType.EXPENSE, source=TransactionSource.MANUAL,
        note=note, occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(transaction)
    db_session.commit()
    return transaction




def test_generate_category_correction_suggestion(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790008001")
    food = Category(name="مطاعم", icon="utensils", is_default=True, category_type=CategoryType.EXPENSE)
    db_session.add(food)
    db_session.commit()

    fake = FakeJsonProvider(f'{{"category_id": "{food.id}", "reasoning": "يبدو أنها مطعم"}}')
    patch_provider(monkeypatch, fake)

    add_uncategorized_transaction(db_session, user)

    response = client.post("/api/v1/agent/actions/check", headers=headers)
    assert response.status_code == 200
    actions = response.json()
    assert len(actions) == 1
    assert actions[0]["action_type"] == "suggest_category_correction"
    assert actions[0]["status"] == "pending"
    assert actions[0]["payload"]["new_category_id"] == str(food.id)


def test_ignores_ai_suggestion_with_unknown_category_id(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790008002")
    fake = FakeJsonProvider('{"category_id": "00000000-0000-0000-0000-000000000000", "reasoning": "x"}')
    patch_provider(monkeypatch, fake)

    add_uncategorized_transaction(db_session, user)

    response = client.post("/api/v1/agent/actions/check", headers=headers)
    assert response.json() == []


def test_ignores_malformed_ai_json(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790008003")
    fake = FakeJsonProvider("مش JSON إطلاقًا")
    patch_provider(monkeypatch, fake)

    add_uncategorized_transaction(db_session, user)

    response = client.post("/api/v1/agent/actions/check", headers=headers)
    assert response.json() == []


def test_confirm_category_correction_applies_it(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790008004")
    food = Category(name="مطاعم", icon="utensils", is_default=True, category_type=CategoryType.EXPENSE)
    db_session.add(food)
    db_session.commit()

    fake = FakeJsonProvider(f'{{"category_id": "{food.id}", "reasoning": "يبدو أنها مطعم"}}')
    patch_provider(monkeypatch, fake)

    transaction = add_uncategorized_transaction(db_session, user)

    check_response = client.post("/api/v1/agent/actions/check", headers=headers)
    action_id = check_response.json()[0]["id"]

    confirm_response = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers)
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "applied"

    db_session.refresh(transaction)
    assert str(transaction.category_id) == str(food.id)


def test_reject_action_does_not_apply_it(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790008005")
    food = Category(name="مطاعم", icon="utensils", is_default=True, category_type=CategoryType.EXPENSE)
    db_session.add(food)
    db_session.commit()

    fake = FakeJsonProvider(f'{{"category_id": "{food.id}", "reasoning": "يبدو أنها مطعم"}}')
    patch_provider(monkeypatch, fake)

    transaction = add_uncategorized_transaction(db_session, user)

    check_response = client.post("/api/v1/agent/actions/check", headers=headers)
    action_id = check_response.json()[0]["id"]

    reject_response = client.post(f"/api/v1/agent/actions/{action_id}/reject", headers=headers)
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"

    db_session.refresh(transaction)
    assert transaction.category_id is None


def test_no_duplicate_suggestions_for_same_transaction(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790008006")
    food = Category(name="مطاعم", icon="utensils", is_default=True, category_type=CategoryType.EXPENSE)
    db_session.add(food)
    db_session.commit()

    fake = FakeJsonProvider(f'{{"category_id": "{food.id}", "reasoning": "يبدو أنها مطعم"}}')
    patch_provider(monkeypatch, fake)

    add_uncategorized_transaction(db_session, user)

    client.post("/api/v1/agent/actions/check", headers=headers)
    second_check = client.post("/api/v1/agent/actions/check", headers=headers)
    assert second_check.json() == []
    assert len(fake.calls) == 1


def test_confirming_already_handled_action_fails(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790008007")
    food = Category(name="مطاعم", icon="utensils", is_default=True, category_type=CategoryType.EXPENSE)
    db_session.add(food)
    db_session.commit()

    fake = FakeJsonProvider(f'{{"category_id": "{food.id}", "reasoning": "x"}}')
    patch_provider(monkeypatch, fake)

    add_uncategorized_transaction(db_session, user)
    check_response = client.post("/api/v1/agent/actions/check", headers=headers)
    action_id = check_response.json()[0]["id"]

    client.post(f"/api/v1/agent/actions/{action_id}/reject", headers=headers)
    second_confirm = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers)
    assert second_confirm.status_code == 400




def test_goal_contribution_suggested_when_energized(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790008008")
    fake = FakeJsonProvider("{}")
    patch_provider(monkeypatch, fake)

    goal = db_session.query(Goal).filter(Goal.user_id == user.id).first()
    goal.current_amount = 900
    db_session.commit()

    response = client.post("/api/v1/agent/actions/check", headers=headers)
    actions = [a for a in response.json() if a["action_type"] == "suggest_goal_contribution"]
    assert len(actions) == 1
    assert actions[0]["payload"]["amount"] > 0
    assert len(fake.calls) == 0


def test_no_goal_contribution_when_not_energized(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790008009")
    fake = FakeJsonProvider("{}")
    patch_provider(monkeypatch, fake)

    response = client.post("/api/v1/agent/actions/check", headers=headers)
    actions = [a for a in response.json() if a["action_type"] == "suggest_goal_contribution"]
    assert len(actions) == 0


def test_confirm_goal_contribution_updates_goal(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790008010")
    fake = FakeJsonProvider("{}")
    patch_provider(monkeypatch, fake)

    goal = db_session.query(Goal).filter(Goal.user_id == user.id).first()
    goal.current_amount = 900
    db_session.commit()
    before_amount = float(goal.current_amount)

    check_response = client.post("/api/v1/agent/actions/check", headers=headers)
    action = next(a for a in check_response.json() if a["action_type"] == "suggest_goal_contribution")

    confirm_response = client.post(f"/api/v1/agent/actions/{action['id']}/confirm", headers=headers)
    assert confirm_response.status_code == 200

    db_session.refresh(goal)
    assert float(goal.current_amount) > before_amount


def test_list_pending_actions(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790008011")
    fake = FakeJsonProvider("{}")
    patch_provider(monkeypatch, fake)

    goal = db_session.query(Goal).filter(Goal.user_id == user.id).first()
    goal.current_amount = 900
    db_session.commit()

    client.post("/api/v1/agent/actions/check", headers=headers)
    list_response = client.get("/api/v1/agent/actions", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
