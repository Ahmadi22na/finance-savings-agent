"""
R04 — حذف الحساب وكل بياناته: كامل، محصور بصاحب الحساب، ومحمي بكلمة المرور.
"""
from datetime import datetime, timezone

from app.models.agent import AgentAction, AgentActionStatus, AgentActionType, AgentInteraction, InteractionTrigger
from app.models.ai_usage import AiUsageEvent
from app.models.category import Category, CategoryType
from app.models.goal import Goal
from app.models.income_allocation import IncomeAllocation
from app.models.transaction import Transaction
from app.models.user import User
from tests.test_income_and_goal_delete import register_with_persona

PASSWORD = "testpassword123"  # نفس كلمة مرور register_with_persona


def populate(client, db_session, headers, user):
    """بيعبّي حساب بكل أنواع البيانات الي بتنحذف."""
    goal = client.post("/api/v1/goals", headers=headers, json={"title": "لابتوب جديد", "target_amount": 600}).json()
    income = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 100, "type": "income", "note": "دخل",
    }).json()
    client.post("/api/v1/transactions/quick-log", headers=headers, json={"amount": 5, "type": "expense", "note": "قهوة"})
    allocation = client.post(f"/api/v1/transactions/{income['id']}/allocate", headers=headers, json={
        "allocations": [{"goal_id": goal["id"], "amount": 40}],
    })
    assert allocation.status_code == 200
    db_session.add(Category(
        name="تصنيفي الخاص", icon="tag", is_default=False, category_type=CategoryType.EXPENSE, user_id=user.id, keywords=[],
    ))
    db_session.add(AgentInteraction(
        user_id=user.id, trigger_type=InteractionTrigger.USER_CHAT, message="سر", is_from_user=True,
    ))
    db_session.add(AgentAction(
        user_id=user.id, action_type=AgentActionType.SUGGEST_INCOME_LOG, status=AgentActionStatus.PENDING,
        payload={"amount": 5}, reasoning="x",
    ))
    db_session.add(AiUsageEvent(user_id=user.id, kind="chat", created_at=datetime.now(timezone.utc)))
    db_session.commit()


def rows_for(db_session, user_id):
    return {
        "users": db_session.query(User).filter(User.id == user_id).count(),
        "goals": db_session.query(Goal).filter(Goal.user_id == user_id).count(),
        "transactions": db_session.query(Transaction).filter(Transaction.user_id == user_id).count(),
        "interactions": db_session.query(AgentInteraction).filter(AgentInteraction.user_id == user_id).count(),
        "actions": db_session.query(AgentAction).filter(AgentAction.user_id == user_id).count(),
        "usage": db_session.query(AiUsageEvent).filter(AiUsageEvent.user_id == user_id).count(),
        "categories": db_session.query(Category).filter(Category.user_id == user_id).count(),
    }


def delete_account(client, headers, password=PASSWORD, confirm=True):
    return client.request("DELETE", "/api/v1/users/me", headers=headers, json={"password": password, "confirm": confirm})


def test_delete_removes_everything_and_leaves_other_users_untouched(client, db_session):
    headers_a, user_a = register_with_persona(client, db_session, "0790120001")
    headers_b, user_b = register_with_persona(client, db_session, "0790120002")
    populate(client, db_session, headers_a, user_a)
    populate(client, db_session, headers_b, user_b)
    default_categories = db_session.query(Category).filter(Category.is_default.is_(True)).count()
    before_b = rows_for(db_session, user_b.id)
    assert all(count >= 1 for count in rows_for(db_session, user_a.id).values())

    response = delete_account(client, headers_a)

    assert response.status_code == 204
    assert rows_for(db_session, user_a.id) == {key: 0 for key in before_b}
    assert db_session.query(IncomeAllocation).count() == 1  # توزيع المستخدم B بس
    assert rows_for(db_session, user_b.id) == before_b
    assert db_session.query(Category).filter(Category.is_default.is_(True)).count() == default_categories


def test_wrong_password_deletes_nothing(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790120003")
    populate(client, db_session, headers, user)
    before = rows_for(db_session, user.id)

    response = delete_account(client, headers, password="غلط-غلط-غلط")

    assert response.status_code == 400
    assert response.json()["detail"] == "كلمة المرور غير صحيحة"
    assert rows_for(db_session, user.id) == before


def test_confirmation_flag_is_mandatory(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790120004")
    assert delete_account(client, headers, confirm=False).status_code == 422
    missing = client.request("DELETE", "/api/v1/users/me", headers=headers, json={"password": PASSWORD})
    assert missing.status_code == 422
    assert db_session.query(User).filter(User.id == user.id).count() == 1


def test_requires_authentication(client):
    response = client.request("DELETE", "/api/v1/users/me", json={"password": PASSWORD, "confirm": True})
    assert response.status_code == 401


def test_token_is_invalid_after_deletion_and_phone_can_be_reused(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790120005")
    assert delete_account(client, headers).status_code == 204

    assert client.get("/api/v1/users/me", headers=headers).status_code == 401
    assert delete_account(client, headers).status_code == 401  # ما بتنحذف مرتين

    again = client.post("/api/v1/auth/register", json={
        "name": "حساب جديد", "phone": "0790120005", "password": PASSWORD,
    })
    assert again.status_code == 201
