"""
الدفعة 0.C — سجل حركة الأهداف (goal_movements) والذرّية.
تشتغل على SQLite وPostgreSQL (اختبارات التزامن الحقيقي بـ tests/pg/test_pg_concurrency.py).
"""
import uuid
from decimal import Decimal

import pytest

from app.models.goal import Goal, GoalStatus
from app.models.goal_movement import GoalMovement
from app.models.income_allocation import IncomeAllocation
from app.services import goal_service
from tests.test_agent_actions import FakeJsonProvider, patch_provider
from tests.test_agent_actions import register_with_persona as register_agent_user
from tests.test_income_and_goal_delete import register_with_persona

PASSWORD = "testpassword123"


def _make_goal(client, headers, title="هدف", target=1000, recurring=False):
    body = {"title": title, "target_amount": target}
    if recurring:
        body["is_recurring"] = True
    response = client.post("/api/v1/goals", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _make_income(client, headers, amount):
    response = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": amount, "type": "income", "note": "راتب",
    })
    assert response.status_code == 201, response.text
    return response.json()


def _movements(db_session, goal_id):
    db_session.expire_all()
    return (
        db_session.query(GoalMovement)
        .filter(GoalMovement.goal_id == uuid.UUID(str(goal_id)))
        .order_by(GoalMovement.created_at, GoalMovement.kind)
        .all()
    )


def _assert_ledger_matches(db_session, goal_id):
    """الثابت المحوري: current_amount = مجموع حركات الهدف."""
    db_session.expire_all()
    goal = db_session.get(Goal, uuid.UUID(str(goal_id)))
    total = sum((m.amount for m in _movements(db_session, goal_id)), Decimal("0"))
    assert Decimal(goal.current_amount) == total


def test_manual_contribution_writes_a_movement(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790096001")
    goal = _make_goal(client, headers)
    response = client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 25.5})
    assert response.status_code == 200

    movements = _movements(db_session, goal["id"])
    assert [(m.kind, Decimal(m.amount)) for m in movements] == [("manual_contribution", Decimal("25.500"))]
    _assert_ledger_matches(db_session, goal["id"])


def test_allocation_writes_movements_linked_to_the_income(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790096002")
    goal_a, goal_b = _make_goal(client, headers, "هدف أ"), _make_goal(client, headers, "هدف ب")
    income = _make_income(client, headers, 100)

    response = client.post(f"/api/v1/transactions/{income['id']}/allocate", headers=headers, json={
        "allocations": [{"goal_id": goal_a["id"], "amount": 30}, {"goal_id": goal_b["id"], "amount": 20.125}],
    })
    assert response.status_code == 200, response.text

    for goal, expected in ((goal_a, "30.000"), (goal_b, "20.125")):
        movements = _movements(db_session, goal["id"])
        assert len(movements) == 1
        assert movements[0].kind == "allocation"
        assert str(movements[0].transaction_id) == income["id"]
        assert Decimal(movements[0].amount) == Decimal(expected)
        _assert_ledger_matches(db_session, goal["id"])


def test_failure_midway_in_allocation_rolls_everything_back(client, db_session, monkeypatch):
    headers, _ = register_with_persona(client, db_session, "0790096003")
    goal_a, goal_b = _make_goal(client, headers, "هدف أ"), _make_goal(client, headers, "هدف ب")
    income = _make_income(client, headers, 100)

    real = goal_service.apply_contribution
    calls = {"count": 0}

    def flaky(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("فشل مصطنع بنص التوزيع")
        return real(*args, **kwargs)

    monkeypatch.setattr(goal_service, "apply_contribution", flaky)

    with pytest.raises(RuntimeError):
        client.post(f"/api/v1/transactions/{income['id']}/allocate", headers=headers, json={
            "allocations": [{"goal_id": goal_a["id"], "amount": 30}, {"goal_id": goal_b["id"], "amount": 20}],
        })

    db_session.expire_all()
    for goal in (goal_a, goal_b):
        assert Decimal(db_session.get(Goal, uuid.UUID(goal["id"])).current_amount) == 0
        assert _movements(db_session, goal["id"]) == []
    assert db_session.query(IncomeAllocation).count() == 0


def test_agent_confirmation_writes_a_movement(client, db_session, monkeypatch):
    headers, user = register_agent_user(client, db_session, "0790096004")
    patch_provider(monkeypatch, FakeJsonProvider("{}"))

    goal = db_session.query(Goal).filter(Goal.user_id == user.id).first()
    goal.current_amount = 900
    db_session.commit()

    check = client.post("/api/v1/agent/actions/check", headers=headers)
    action = next(a for a in check.json() if a["action_type"] == "suggest_goal_contribution")
    assert client.post(f"/api/v1/agent/actions/{action['id']}/confirm", headers=headers).status_code == 200

    movements = _movements(db_session, goal.id)
    assert len(movements) == 1
    assert movements[0].kind == "agent_contribution"
    assert Decimal(movements[0].amount) > 0


def test_agent_contribution_to_a_non_active_goal_is_rejected(client, db_session, monkeypatch):
    """قرار معتمد: مسار رشيد يمر من نفس بوابة المساهمة، فيحترم شرط الهدف النشط."""
    headers, user = register_agent_user(client, db_session, "0790096005")
    patch_provider(monkeypatch, FakeJsonProvider("{}"))

    goal = db_session.query(Goal).filter(Goal.user_id == user.id).first()
    goal.current_amount = 900
    db_session.commit()
    check = client.post("/api/v1/agent/actions/check", headers=headers)
    action = next(a for a in check.json() if a["action_type"] == "suggest_goal_contribution")

    goal.status = GoalStatus.ABANDONED
    db_session.commit()
    response = client.post(f"/api/v1/agent/actions/{action['id']}/confirm", headers=headers)
    assert response.status_code == 400
    assert _movements(db_session, goal.id) == []


def test_recurring_reset_is_a_negative_movement_and_keeps_the_ledger_balanced(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790096006")
    goal = _make_goal(client, headers, "اشتراك", target=40, recurring=True)
    assert client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 40}).status_code == 200

    db_goal = db_session.get(Goal, uuid.UUID(goal["id"]))
    db_goal.last_reset_month = "2000-01"
    db_session.commit()

    listed = client.get("/api/v1/goals", headers=headers).json()
    entry = next(g for g in listed if g["id"] == goal["id"])
    assert entry["current_amount"] == 0 and entry["status"] == "active"

    movements = _movements(db_session, goal["id"])
    assert sorted(m.kind for m in movements) == ["cycle_reset", "manual_contribution"]
    reset = next(m for m in movements if m.kind == "cycle_reset")
    assert Decimal(reset.amount) == Decimal("-40.000")
    assert reset.cycle == "2000-01"  # بدورة الشهر القديم
    _assert_ledger_matches(db_session, goal["id"])


def test_goal_deletion_removes_its_movements(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790096007")
    goal = _make_goal(client, headers)
    client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 10})
    assert len(_movements(db_session, goal["id"])) == 1

    assert client.delete(f"/api/v1/goals/{goal['id']}", headers=headers).status_code == 204
    assert db_session.query(GoalMovement).count() == 0


def test_account_deletion_removes_movements(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790096008")
    goal = _make_goal(client, headers)
    client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 10})
    assert db_session.query(GoalMovement).count() == 1

    response = client.request("DELETE", "/api/v1/users/me", headers=headers, json={"password": PASSWORD, "confirm": True})
    assert response.status_code == 204, response.text
    db_session.expire_all()
    assert db_session.query(GoalMovement).count() == 0
