"""
الدفعة 0.D — تعديل وحذف المعاملات مع سلامة التوزيعات والأهداف.
تشتغل على SQLite وPostgreSQL (التزامن الحقيقي بـ tests/pg/test_pg_edit_delete_concurrency.py).
"""
import uuid
from decimal import Decimal

from app.models.goal import Goal
from app.models.goal_movement import GoalMovement
from app.models.income_allocation import IncomeAllocation
from app.models.transaction import Transaction
from tests.test_income_and_goal_delete import register_with_persona


def _goal(client, headers, title="هدف تجريبي", target=1000, recurring=False):
    body = {"title": title, "target_amount": target}
    if recurring:
        body["is_recurring"] = True
    response = client.post("/api/v1/goals", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _tx(client, headers, amount, type_="expense", note="اختبار"):
    response = client.post("/api/v1/transactions/quick-log", headers=headers, json={"amount": amount, "type": type_, "note": note})
    assert response.status_code == 201, response.text
    return response.json()


def _allocate(client, headers, income_id, parts):
    response = client.post(f"/api/v1/transactions/{income_id}/allocate", headers=headers, json={
        "allocations": [{"goal_id": goal_id, "amount": amount} for goal_id, amount in parts],
    })
    assert response.status_code == 200, response.text
    return response.json()


def _goal_state(client, headers, goal_id):
    return next(g for g in client.get("/api/v1/goals", headers=headers).json() if g["id"] == goal_id)


def _assert_ledger_matches(db_session, goal_id):
    db_session.expire_all()
    goal = db_session.get(Goal, uuid.UUID(goal_id))
    moved = sum(
        (m.amount for m in db_session.query(GoalMovement).filter(GoalMovement.goal_id == goal.id).all()), Decimal("0")
    )
    assert Decimal(goal.current_amount) == moved


# ---------------------------------------------------------------- الحذف

def test_delete_expense(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790098001")
    tx = _tx(client, headers, 5)
    assert client.delete(f"/api/v1/transactions/{tx['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/transactions/{tx['id']}", headers=headers).status_code == 404
    assert all(t["id"] != tx["id"] for t in client.get("/api/v1/transactions", headers=headers).json())


def test_delete_income_without_allocations(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790098002")
    tx = _tx(client, headers, 50, "income")
    assert client.delete(f"/api/v1/transactions/{tx['id']}", headers=headers).status_code == 204


def test_delete_allocated_income_reverses_the_goals(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790098003")
    goal_a, goal_b = _goal(client, headers, "هدف أ", 30), _goal(client, headers, "هدف ب", 500)
    income = _tx(client, headers, 100, "income")
    _allocate(client, headers, income["id"], [(goal_a["id"], 30), (goal_b["id"], 20.125)])
    assert _goal_state(client, headers, goal_a["id"])["status"] == "achieved"

    assert client.delete(f"/api/v1/transactions/{income['id']}", headers=headers).status_code == 204

    a, b = _goal_state(client, headers, goal_a["id"]), _goal_state(client, headers, goal_b["id"])
    assert a["current_amount"] == 0 and a["status"] == "active"  # رجع نشط بعد ما نزل تحت الهدف
    assert b["current_amount"] == 0
    assert db_session.query(IncomeAllocation).count() == 0
    for goal in (goal_a, goal_b):
        db_session.expire_all()
        kinds = sorted(m.kind for m in db_session.query(GoalMovement).filter(GoalMovement.goal_id == uuid.UUID(goal["id"])))
        assert kinds == ["allocation", "reversal"]
        _assert_ledger_matches(db_session, goal["id"])
    assert db_session.query(GoalMovement).filter(GoalMovement.transaction_id.isnot(None)).count() == 0


def test_deleting_one_income_reverses_only_its_share(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790098004")
    goal = _goal(client, headers)
    income_a, income_b = _tx(client, headers, 100, "income"), _tx(client, headers, 100, "income")
    _allocate(client, headers, income_a["id"], [(goal["id"], 30)])
    _allocate(client, headers, income_b["id"], [(goal["id"], 20)])

    assert client.delete(f"/api/v1/transactions/{income_a['id']}", headers=headers).status_code == 204
    assert _goal_state(client, headers, goal["id"])["current_amount"] == 20
    _assert_ledger_matches(db_session, goal["id"])


def test_manual_contributions_survive_income_deletion(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790098005")
    goal = _goal(client, headers)
    income = _tx(client, headers, 100, "income")
    client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 10})
    _allocate(client, headers, income["id"], [(goal["id"], 30)])

    client.delete(f"/api/v1/transactions/{income['id']}", headers=headers)
    assert _goal_state(client, headers, goal["id"])["current_amount"] == 10
    _assert_ledger_matches(db_session, goal["id"])


def test_old_cycle_allocation_does_not_touch_the_new_cycle(client, db_session):
    """القاعدة المعتمدة: هدف متكرر انصفّر بشهر جديد، وانحذف دخل من الشهر القديم → مبلغ الشهر الجديد ما بيتأثر."""
    headers, _ = register_with_persona(client, db_session, "0790098006")
    goal = _goal(client, headers, "اشتراك", target=40, recurring=True)
    income = _tx(client, headers, 100, "income")
    _allocate(client, headers, income["id"], [(goal["id"], 40)])  # منجز بالدورة الحالية

    # نحاكي إنه التوزيع كان بشهر قديم: دورته القديمة + الهدف عالق على نفس الدورة القديمة
    db_session.query(GoalMovement).update({GoalMovement.cycle: "2000-01"})
    db_goal = db_session.get(Goal, uuid.UUID(goal["id"]))
    db_goal.last_reset_month = "2000-01"
    db_session.commit()

    state = _goal_state(client, headers, goal["id"])  # القراءة بتطلّق التصفير الشهري
    assert state["current_amount"] == 0 and state["status"] == "active"
    client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 10})  # مبلغ الدورة الجديدة

    assert client.delete(f"/api/v1/transactions/{income['id']}", headers=headers).status_code == 204
    assert _goal_state(client, headers, goal["id"])["current_amount"] == 10  # ما نقص شي
    _assert_ledger_matches(db_session, goal["id"])


def test_legacy_allocation_without_movement_is_reversed_for_non_recurring_goals(client, db_session):
    """توزيعات قبل 0.C (بدون حركة بالسجل): بنعكسها للهدف غير المتكرر، بدون ما نكسر تطابق السجل."""
    headers, _ = register_with_persona(client, db_session, "0790098007")
    goal = _goal(client, headers)
    income = _tx(client, headers, 100, "income")
    _allocate(client, headers, income["id"], [(goal["id"], 30)])
    # نحاكي ترحيل 0.C: الحركة تتحول لـ opening بدون ربط بالمعاملة
    db_session.query(GoalMovement).update({GoalMovement.kind: "opening", GoalMovement.transaction_id: None})
    db_session.commit()

    assert client.delete(f"/api/v1/transactions/{income['id']}", headers=headers).status_code == 204
    assert _goal_state(client, headers, goal["id"])["current_amount"] == 0
    _assert_ledger_matches(db_session, goal["id"])


def test_cannot_delete_or_edit_someone_elses_transaction(client, db_session):
    headers1, _ = register_with_persona(client, db_session, "0790098008")
    headers2, _ = register_with_persona(client, db_session, "0790098009")
    tx = _tx(client, headers1, 5)
    assert client.delete(f"/api/v1/transactions/{tx['id']}", headers=headers2).status_code == 404
    assert client.patch(f"/api/v1/transactions/{tx['id']}", headers=headers2, json={"amount": 6}).status_code == 404
    assert db_session.query(Transaction).count() >= 1


def test_delete_requires_authentication(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790098010")
    tx = _tx(client, headers, 5)
    assert client.delete(f"/api/v1/transactions/{tx['id']}").status_code == 401


# ---------------------------------------------------------------- التعديل

def test_edit_expense_amount_note_and_time(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790098011")
    tx = _tx(client, headers, 5)
    response = client.patch(f"/api/v1/transactions/{tx['id']}", headers=headers, json={
        "amount": 7.125, "note": "  غدا  ", "occurred_at": "2026-01-05T10:00:00Z",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["amount"] == 7.125 and body["note"] == "غدا" and body["occurred_at"].startswith("2026-01-05")


def test_edit_note_to_null_clears_it_and_omitted_fields_do_not_change(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790098012")
    tx = _tx(client, headers, 5, note="ملاحظة")
    cleared = client.patch(f"/api/v1/transactions/{tx['id']}", headers=headers, json={"note": None}).json()
    assert cleared["note"] is None and cleared["amount"] == 5

    only_amount = client.patch(f"/api/v1/transactions/{tx['id']}", headers=headers, json={"amount": 6}).json()
    assert only_amount["amount"] == 6 and only_amount["note"] is None  # الملاحظة ما رجعت ولا انمسح شي ثاني


def test_edit_validation(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790098013")
    tx = _tx(client, headers, 5)
    url = f"/api/v1/transactions/{tx['id']}"
    assert client.patch(url, headers=headers, json={}).status_code == 422
    assert client.patch(url, headers=headers, json={"amount": None}).status_code == 422
    assert client.patch(url, headers=headers, json={"amount": 0}).status_code == 422
    assert client.patch(url, headers=headers, json={"amount": 1.0001}).status_code == 422
    assert client.patch(url, headers=headers, json={"occurred_at": None}).status_code == 422
    assert client.patch(url, headers=headers, json={"amount": 0.1 + 0.2}).status_code == 200  # ضجيج float مقبول


def test_income_cannot_drop_below_the_allocated_amount(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790098014")
    goal = _goal(client, headers)
    income = _tx(client, headers, 100, "income")
    _allocate(client, headers, income["id"], [(goal["id"], 60)])
    url = f"/api/v1/transactions/{income['id']}"

    assert client.patch(url, headers=headers, json={"amount": 59.999}).status_code == 400
    ok = client.patch(url, headers=headers, json={"amount": 60})
    assert ok.status_code == 200 and ok.json()["unallocated_amount"] == 0

    bigger = client.patch(url, headers=headers, json={"amount": 80}).json()
    assert bigger["unallocated_amount"] == 20
    assert _goal_state(client, headers, goal["id"])["current_amount"] == 60  # التعديل ما لمس الهدف


def test_category_patch_still_works_alongside_other_fields(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790098015")
    tx = _tx(client, headers, 5)
    response = client.patch(f"/api/v1/transactions/{tx['id']}", headers=headers, json={"category_id": None, "amount": 9})
    assert response.status_code == 200 and response.json()["amount"] == 9
