"""Module documentation."""
import uuid

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


    persona = db_session.query(Persona).filter(Persona.key == "wise").first()
    if persona is None:
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


def test_income_and_goal_proposal_in_same_reply_dont_leak_markers_into_reasoning(
    client, db_session, monkeypatch
):
    """Test income and goal proposal in same reply dont leak markers into reasoning documentation."""
    headers, user = register_with_persona(client, db_session, "0790010013")
    reply_text = (
        'تمام يا أستاذ، سجلتلك الدخل. وجهزتلك خطة لهدفك كمان. '
        '<<<INCOME_LOG_PROPOSAL>>>{"amount": 25, "note": "شغل يوم"}<<<END>>>'
        '<<<GOAL_PROPOSAL>>>{"title": "ملابس نهاية السنة", "target_amount": 200}<<<END>>>'
    )
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    response = client.post("/api/v1/agent/chat", headers=headers, json={
        "message": "اجاني 25 دينار، وبدي أوفر 200 دينار لملابس آخر السنة",
    })
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "<<<" not in reply and ">>>" not in reply

    pending = agent_action_service.list_pending_actions(db_session, user)
    income_action = next(a for a in pending if a.action_type.value == "suggest_income_log")
    goal_action = next(a for a in pending if a.action_type.value == "suggest_goal_creation")


    for action in (income_action, goal_action):
        assert "<<<" not in action.reasoning
        assert ">>>" not in action.reasoning


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
    """Test income report does not trigger goal creation documentation."""
    headers, user = register_with_persona(client, db_session, "0790010003")
    reply_text = '<<<INCOME_LOG_PROPOSAL>>>{"amount": 25, "note": "شغل يوم"}<<<END>>>'
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    client.post("/api/v1/agent/chat", headers=headers, json={"message": "اجاني 25 دينار"})

    pending = agent_action_service.list_pending_actions(db_session, user)
    goal_proposals = [a for a in pending if a.action_type.value == "suggest_goal_creation"]
    assert len(goal_proposals) == 0




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




def test_new_goal_gets_next_priority_after_existing_ones(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010008")
    first = client.post("/api/v1/goals", headers=headers, json={
        "title": "أول خطة", "target_amount": 100,
    }).json()
    second = client.post("/api/v1/goals", headers=headers, json={
        "title": "ثاني خطة", "target_amount": 100,
    }).json()

    assert second["priority"] > first["priority"]


def test_reorder_goals_updates_priority_and_list_order(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010009")
    goal_a = client.post("/api/v1/goals", headers=headers, json={
        "title": "أا", "target_amount": 100,
    }).json()
    goal_b = client.post("/api/v1/goals", headers=headers, json={
        "title": "بب", "target_amount": 100,
    }).json()
    goal_c = client.post("/api/v1/goals", headers=headers, json={
        "title": "جج", "target_amount": 100,
    }).json()



    existing_ids = [g["id"] for g in client.get("/api/v1/goals", headers=headers).json()]
    onboarding_goal_id = next(
        gid for gid in existing_ids
        if gid not in (goal_a["id"], goal_b["id"], goal_c["id"])
    )

    new_order = [goal_c["id"], goal_a["id"], onboarding_goal_id, goal_b["id"]]
    response = client.put(
        "/api/v1/goals/reorder", headers=headers, json={"ordered_goal_ids": new_order}
    )
    assert response.status_code == 200

    list_response = client.get("/api/v1/goals", headers=headers)
    active_ids_in_order = [g["id"] for g in list_response.json()]
    assert active_ids_in_order == new_order


def test_reorder_rejects_incomplete_goal_list(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010010")
    goal_a = client.post("/api/v1/goals", headers=headers, json={
        "title": "أا", "target_amount": 100,
    }).json()
    client.post("/api/v1/goals", headers=headers, json={
        "title": "بب", "target_amount": 100,
    })

    response = client.put(
        "/api/v1/goals/reorder", headers=headers, json={"ordered_goal_ids": [goal_a["id"]]}
    )
    assert response.status_code == 400


def test_reorder_rejects_goal_belonging_to_another_user(client, db_session):
    headers1, user1 = register_with_persona(client, db_session, "0790010011")
    headers2, user2 = register_with_persona(client, db_session, "0790010012")

    goal1 = client.post("/api/v1/goals", headers=headers1, json={
        "title": "خطتي", "target_amount": 100,
    }).json()
    client.post("/api/v1/goals", headers=headers2, json={
        "title": "خطة غيري", "target_amount": 100,
    })

    response = client.put(
        "/api/v1/goals/reorder", headers=headers2, json={"ordered_goal_ids": [goal1["id"]]}
    )
    assert response.status_code == 400




def test_recurring_goal_created_with_current_month_marked(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010014")
    response = client.post("/api/v1/goals", headers=headers, json={
        "title": "إيجار", "target_amount": 150, "is_recurring": True,
    })
    assert response.status_code == 201
    assert response.json()["is_recurring"] is True


def test_recurring_goal_achieved_this_month_stays_achieved(client, db_session):
    """Test recurring goal achieved this month stays achieved documentation."""
    headers, user = register_with_persona(client, db_session, "0790010015")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "اشتراك", "target_amount": 20, "is_recurring": True,
    }).json()

    client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 20})

    listing = client.get("/api/v1/goals", headers=headers).json()
    updated = next(g for g in listing if g["id"] == goal["id"])
    assert updated["status"] == "achieved"
    assert updated["current_amount"] == 20.0


def test_recurring_goal_resets_when_month_changes(client, db_session, monkeypatch):
    """Test recurring goal resets when month changes documentation."""
    headers, user = register_with_persona(client, db_session, "0790010016")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "اشتراك", "target_amount": 20, "is_recurring": True,
    }).json()
    client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 20})

    from app.models.goal import Goal, GoalStatus
    db_goal = db_session.query(Goal).filter(Goal.id == uuid.UUID(goal["id"])).first()
    assert db_goal.status == GoalStatus.ACHIEVED
    db_goal.last_reset_month = "2000-01"
    db_session.commit()

    listing = client.get("/api/v1/goals", headers=headers).json()
    reset_goal = next(g for g in listing if g["id"] == goal["id"])
    assert reset_goal["status"] == "active"
    assert reset_goal["current_amount"] == 0.0


def test_non_recurring_goal_never_auto_resets(client, db_session):
    """Test non recurring goal never auto resets documentation."""
    headers, user = register_with_persona(client, db_session, "0790010017")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "هدف عادي", "target_amount": 20,
    }).json()
    client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 20})

    from app.models.goal import Goal
    db_goal = db_session.query(Goal).filter(Goal.id == uuid.UUID(goal["id"])).first()
    db_goal.last_reset_month = "2000-01"
    db_session.commit()

    listing = client.get("/api/v1/goals", headers=headers).json()
    unchanged = next(g for g in listing if g["id"] == goal["id"])
    assert unchanged["status"] == "achieved"
    assert unchanged["current_amount"] == 20.0


def test_chat_goal_proposal_with_is_recurring_creates_recurring_goal(
    client, db_session, monkeypatch
):
    """Test chat goal proposal with is recurring creates recurring goal documentation."""
    headers, user = register_with_persona(client, db_session, "0790010018")
    reply_text = (
        'ظبطتلك! <<<GOAL_PROPOSAL>>>{"title": "إيجار البيت", "target_amount": 150, '
        '"breakdown": [], "is_recurring": true}<<<END>>>'
    )
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    client.post("/api/v1/agent/chat", headers=headers, json={
        "message": "بدي أخصص لإيجار البيت كل شهر 150 دينار",
    })

    pending = agent_action_service.list_pending_actions(db_session, user)
    action = next(a for a in pending if a.action_type.value == "suggest_goal_creation")
    assert action.payload["is_recurring"] is True

    confirm_response = client.post(
        f"/api/v1/agent/actions/{action.id}/confirm", headers=headers
    )
    assert confirm_response.status_code == 200

    from app.models.goal import Goal
    new_goal = db_session.query(Goal).filter(Goal.title == "إيجار البيت").first()
    assert new_goal is not None
    assert new_goal.is_recurring is True
    assert new_goal.last_reset_month is not None




def test_duplicate_goal_proposal_within_window_is_not_duplicated(client, db_session, monkeypatch):
    """Test duplicate goal proposal within window is not duplicated documentation."""
    headers, user = register_with_persona(client, db_session, "0790010019")
    reply_text = (
        'ظبطتلك! <<<GOAL_PROPOSAL>>>{"title": "إيجار البيت", "target_amount": 150, '
        '"breakdown": [], "is_recurring": true}<<<END>>>'
    )
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    message = {"message": "بدي أخصص لإيجار البيت كل شهر 150 دينار"}
    client.post("/api/v1/agent/chat", headers=headers, json=message)
    client.post("/api/v1/agent/chat", headers=headers, json=message)

    pending = agent_action_service.list_pending_actions(db_session, user)
    goal_actions = [a for a in pending if a.action_type.value == "suggest_goal_creation"]
    assert len(goal_actions) == 1


def test_different_income_amounts_are_not_treated_as_duplicates(client, db_session, monkeypatch):
    """Test different income amounts are not treated as duplicates documentation."""
    headers, user = register_with_persona(client, db_session, "0790010020")

    fake = FakeReplyProvider(
        'تمام! <<<INCOME_LOG_PROPOSAL>>>{"amount": 25, "note": "شغل يوم"}<<<END>>>'
    )
    patch_provider(monkeypatch, fake)
    client.post("/api/v1/agent/chat", headers=headers, json={"message": "اجاني 25 دينار"})

    fake.text = 'تمام! <<<INCOME_LOG_PROPOSAL>>>{"amount": 40, "note": "شغل يوم تاني"}<<<END>>>'
    client.post("/api/v1/agent/chat", headers=headers, json={"message": "اجاني 40 دينار كمان"})

    pending = agent_action_service.list_pending_actions(db_session, user)
    income_actions = [a for a in pending if a.action_type.value == "suggest_income_log"]
    assert len(income_actions) == 2




def test_new_income_transaction_starts_fully_unallocated(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010021")
    response = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 100, "type": "income", "note": "راتب",
    })
    assert response.status_code == 201
    assert response.json()["unallocated_amount"] == 100.0


def test_allocate_income_splits_across_two_goals(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010022")
    goal_a = client.post("/api/v1/goals", headers=headers, json={
        "title": "سفر", "target_amount": 500,
    }).json()
    goal_b = client.post("/api/v1/goals", headers=headers, json={
        "title": "مصاريف", "target_amount": 500,
    }).json()
    transaction = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 300, "type": "income", "note": "راتب",
    }).json()

    response = client.post(
        f"/api/v1/transactions/{transaction['id']}/allocate", headers=headers,
        json={"allocations": [
            {"goal_id": goal_a["id"], "amount": 150},
            {"goal_id": goal_b["id"], "amount": 100},
        ]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transaction"]["unallocated_amount"] == 50.0

    updated_by_id = {g["id"]: g for g in body["updated_goals"]}
    assert updated_by_id[goal_a["id"]]["current_amount"] == 150.0
    assert updated_by_id[goal_b["id"]]["current_amount"] == 100.0


def test_allocate_income_rejects_amount_over_available(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010023")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "سفر", "target_amount": 500,
    }).json()
    transaction = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 50, "type": "income", "note": "شغل يوم",
    }).json()

    response = client.post(
        f"/api/v1/transactions/{transaction['id']}/allocate", headers=headers,
        json={"allocations": [{"goal_id": goal["id"], "amount": 999}]},
    )
    assert response.status_code == 400


def test_allocate_income_rejects_non_income_transaction(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010024")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "سفر", "target_amount": 500,
    }).json()
    expense = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 20, "type": "expense", "note": "بقالة",
    }).json()

    response = client.post(
        f"/api/v1/transactions/{expense['id']}/allocate", headers=headers,
        json={"allocations": [{"goal_id": goal["id"], "amount": 10}]},
    )
    assert response.status_code == 400


def test_allocate_income_rejects_achieved_goal(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010025")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "هدف صغير", "target_amount": 20,
    }).json()
    client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 20})

    transaction = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 50, "type": "income", "note": "شغل يوم",
    }).json()
    response = client.post(
        f"/api/v1/transactions/{transaction['id']}/allocate", headers=headers,
        json={"allocations": [{"goal_id": goal["id"], "amount": 10}]},
    )
    assert response.status_code == 400


def test_allocate_income_twice_accumulates_unallocated_correctly(client, db_session):
    """Test allocate income twice accumulates unallocated correctly documentation."""
    headers, user = register_with_persona(client, db_session, "0790010026")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "سفر", "target_amount": 500,
    }).json()
    transaction = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 100, "type": "income", "note": "راتب",
    }).json()

    first = client.post(
        f"/api/v1/transactions/{transaction['id']}/allocate", headers=headers,
        json={"allocations": [{"goal_id": goal["id"], "amount": 40}]},
    )
    assert first.status_code == 200
    assert first.json()["transaction"]["unallocated_amount"] == 60.0


    over = client.post(
        f"/api/v1/transactions/{transaction['id']}/allocate", headers=headers,
        json={"allocations": [{"goal_id": goal["id"], "amount": 61}]},
    )
    assert over.status_code == 400

    second = client.post(
        f"/api/v1/transactions/{transaction['id']}/allocate", headers=headers,
        json={"allocations": [{"goal_id": goal["id"], "amount": 60}]},
    )
    assert second.status_code == 200
    assert second.json()["transaction"]["unallocated_amount"] == 0.0


def test_allocate_income_caps_at_goal_capacity_and_keeps_remainder_unallocated(client, db_session):
    """Test allocate income caps at goal capacity and keeps remainder unallocated documentation."""
    headers, user = register_with_persona(client, db_session, "0790010027")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "هدف صغير", "target_amount": 150,
    }).json()
    transaction = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 300, "type": "income", "note": "دخل كبير",
    }).json()

    response = client.post(
        f"/api/v1/transactions/{transaction['id']}/allocate", headers=headers,
        json={"allocations": [{"goal_id": goal["id"], "amount": 300}]},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["transaction"]["unallocated_amount"] == 150.0
    updated_goal = body["updated_goals"][0]
    assert updated_goal["current_amount"] == 150.0
    assert updated_goal["status"] == "achieved"


def test_partial_allocation_shows_correct_progress(client, db_session):
    """Test partial allocation shows correct progress documentation."""
    headers, user = register_with_persona(client, db_session, "0790010028")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "هدف كبير", "target_amount": 100,
    }).json()
    transaction = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 15, "type": "income", "note": "شغل يوم",
    }).json()

    response = client.post(
        f"/api/v1/transactions/{transaction['id']}/allocate", headers=headers,
        json={"allocations": [{"goal_id": goal["id"], "amount": 15}]},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["transaction"]["unallocated_amount"] == 0.0
    updated_goal = body["updated_goals"][0]
    assert updated_goal["current_amount"] == 15.0
    assert updated_goal["status"] == "active"
    assert updated_goal["progress_percentage"] == 15.0


def test_list_transactions_reports_unallocated_amount_per_transaction(client, db_session):
    """Test list transactions reports unallocated amount per transaction documentation."""
    headers, user = register_with_persona(client, db_session, "0790010029")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "هدف اختبار", "target_amount": 500,
    }).json()
    income = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 100, "type": "income", "note": "راتب",
    }).json()
    untouched_income = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 30, "type": "income", "note": "شغل يوم",
    }).json()
    expense = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 20, "type": "expense", "note": "بقالة",
    }).json()

    client.post(f"/api/v1/transactions/{income['id']}/allocate", headers=headers, json={
        "allocations": [{"goal_id": goal["id"], "amount": 40}],
    })

    listing = {t["id"]: t for t in client.get("/api/v1/transactions", headers=headers).json()}
    assert listing[income["id"]]["unallocated_amount"] == 60.0
    assert listing[untouched_income["id"]]["unallocated_amount"] == 30.0
    assert listing[expense["id"]]["unallocated_amount"] == 0
