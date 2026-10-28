"""
المرحلة 1 / الدفعة 1.B — التحويل الداخلي، ربط المعاملات بالحسابات، واستثناء التحويلات من الدخل والمصروف الحقيقي.
تشتغل على SQLite وPostgreSQL (التزامن الحقيقي بـ tests/pg/test_pg_transfers.py).
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.agent import financial_context, mood_engine
from app.models.category import Category, CategoryType
from app.models.financial_account import FinancialAccount
from app.models.transaction import Transaction, TransactionSource, TransactionType
from app.services import usage_metrics_service
from tests.test_agent_actions import FakeJsonProvider, patch_provider
from tests.test_agent_actions import register_with_persona as register_agent_user
from tests.test_income_and_goal_delete import register_with_persona
from tests.test_usage_metrics import NOW as METRICS_NOW
from tests.test_usage_metrics import add_transaction as add_metrics_transaction
from tests.test_usage_metrics import make_user as make_metrics_user


def _now():
    return datetime.now(timezone.utc)


def _iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _later():
    """وقت بعد لقطات الرصيد الابتدائية (اللي بتتسجّل بوقت الإنشاء) حتى تنحسب الحركة بالرصيد."""
    return _iso(_now() + timedelta(minutes=1))


def _account(client, headers, name, opening=None, kind="cash"):
    body = {"name": name, "kind": kind}
    if opening is not None:
        body["opening_balance"] = opening
    response = client.post("/api/v1/accounts", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _transfer(client, headers, from_id, to_id, amount, **extra):
    return client.post("/api/v1/transfers", headers=headers, json={
        "from_account_id": from_id, "to_account_id": to_id, "amount": amount, **extra,
    })


def _balance(client, headers, account_id):
    return client.get(f"/api/v1/accounts/{account_id}", headers=headers).json()["balance"]


def _transactions(client, headers):
    return client.get("/api/v1/transactions", headers=headers).json()


def _legs(client, headers, group_id):
    return [t for t in _transactions(client, headers) if t["transfer_group_id"] == group_id]


def _make_transfer(client, headers, opening_a=100, opening_b=10, amount=30.125):
    a, b = _account(client, headers, "الأول", opening_a), _account(client, headers, "الثاني", opening_b)
    response = _transfer(client, headers, a["id"], b["id"], amount, occurred_at=_later(), note="تعبئة")
    assert response.status_code == 201, response.text
    return a, b, response.json()


# ------------------------------------------------------------------ إنشاء التحويل

def test_transfer_creates_two_balanced_legs_and_moves_both_balances(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790110001")
    a, b, body = _make_transfer(client, headers)

    assert body["amount"] == 30.125 and body["from_account_id"] == a["id"] and body["to_account_id"] == b["id"]
    assert _balance(client, headers, a["id"]) == 69.875
    assert _balance(client, headers, b["id"]) == 40.125
    assert client.get("/api/v1/accounts/summary", headers=headers).json()["total"] == 110  # التحويل ما بغيّر المجموع

    legs = _legs(client, headers, body["transfer_group_id"])
    assert len(legs) == 2
    by_type = {leg["type"]: leg for leg in legs}
    assert by_type["expense"]["account_id"] == a["id"] and by_type["expense"]["id"] == body["out_transaction_id"]
    assert by_type["income"]["account_id"] == b["id"] and by_type["income"]["id"] == body["in_transaction_id"]
    for leg in legs:
        assert leg["is_transfer"] is True and leg["category"] is None and leg["source"] == "manual"
        assert leg["amount"] == 30.125 and leg["note"] == "تعبئة" and leg["unallocated_amount"] == 0


def test_normal_transactions_have_no_account_and_are_not_transfers(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790110002")
    tx = client.post("/api/v1/transactions/quick-log", headers=headers, json={"amount": 3, "type": "expense", "note": "x"}).json()
    assert tx["account_id"] is None and tx["is_transfer"] is False and tx["transfer_group_id"] is None


def test_transfer_validation_and_ownership(client, db_session):
    headers1, _ = register_with_persona(client, db_session, "0790110003")
    headers2, _ = register_with_persona(client, db_session, "0790110004")
    a, b = _account(client, headers1, "أ", 50), _account(client, headers1, "ب", 5)
    foreign = _account(client, headers2, "غريب", 5)
    archived = _account(client, headers1, "مؤرشف", 5)
    client.patch(f"/api/v1/accounts/{archived['id']}", headers=headers1, json={"is_active": False})

    assert _transfer(client, headers1, a["id"], a["id"], 5).status_code == 400
    assert _transfer(client, headers1, a["id"], foreign["id"], 5).status_code == 404
    assert _transfer(client, headers1, foreign["id"], a["id"], 5).status_code == 404
    assert _transfer(client, headers1, a["id"], str(uuid.uuid4()), 5).status_code == 404
    assert _transfer(client, headers1, a["id"], archived["id"], 5).status_code == 400
    assert _transfer(client, headers1, archived["id"], b["id"], 5).status_code == 400
    for bad_amount in (0, -1, 1.0001, "abc"):
        assert _transfer(client, headers1, a["id"], b["id"], bad_amount).status_code == 422
    assert client.post("/api/v1/transfers", headers=headers1, json={"amount": 5}).status_code == 422
    assert client.post("/api/v1/transfers", json={}).status_code == 401

    assert [t for t in _transactions(client, headers1) if t["is_transfer"]] == []  # ولا طرف تحويل انعمل
    assert _balance(client, headers1, a["id"]) == 50 and _balance(client, headers1, b["id"]) == 5


# ------------------------------------------------------------------ الاستثناء من التوزيع والتصنيف

def test_transfer_legs_cannot_be_allocated(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790110005")
    goal = client.post("/api/v1/goals", headers=headers, json={"title": "هدف", "target_amount": 500}).json()
    _, _, body = _make_transfer(client, headers)
    response = client.post(f"/api/v1/transactions/{body['in_transaction_id']}/allocate", headers=headers, json={
        "allocations": [{"goal_id": goal["id"], "amount": 5}],
    })
    assert response.status_code == 400
    assert client.get("/api/v1/goals", headers=headers).json()[0]["current_amount"] == 0


def test_transfer_legs_reject_a_category_and_an_account_change(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790110006")
    a, b, body = _make_transfer(client, headers)
    url = f"/api/v1/transactions/{body['out_transaction_id']}"
    assert client.patch(url, headers=headers, json={"category_id": None}).status_code == 400
    assert client.patch(url, headers=headers, json={"account_id": b["id"]}).status_code == 400
    assert client.patch(url, headers=headers, json={"account_id": None}).status_code == 400
    assert client.patch(url, headers=headers, json={}).status_code == 422


# ------------------------------------------------------------------ اتساق الطرفين بالتعديل والحذف

def test_editing_one_leg_updates_both_legs_and_both_balances(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790110007")
    a, b, body = _make_transfer(client, headers)
    moved_at = _iso(_now() + timedelta(minutes=2))
    response = client.patch(f"/api/v1/transactions/{body['in_transaction_id']}", headers=headers, json={
        "amount": 40, "note": "  تصحيح  ", "occurred_at": moved_at,
    })
    assert response.status_code == 200, response.text

    legs = _legs(client, headers, body["transfer_group_id"])
    assert len(legs) == 2
    assert {leg["amount"] for leg in legs} == {40} and {leg["note"] for leg in legs} == {"تصحيح"}
    assert {leg["occurred_at"][:16] for leg in legs} == {moved_at[:16]}
    assert _balance(client, headers, a["id"]) == 60 and _balance(client, headers, b["id"]) == 50

    cleared = client.patch(f"/api/v1/transactions/{body['out_transaction_id']}", headers=headers, json={"note": None})
    assert cleared.status_code == 200
    assert {leg["note"] for leg in _legs(client, headers, body["transfer_group_id"])} == {None}


@pytest.mark.parametrize("which", ["out_transaction_id", "in_transaction_id"])
def test_deleting_either_leg_deletes_both_and_restores_balances(client, db_session, which):
    headers, _ = register_with_persona(client, db_session, "0790110008" if which.startswith("out") else "0790110009")
    a, b, body = _make_transfer(client, headers)
    assert client.delete(f"/api/v1/transactions/{body[which]}", headers=headers).status_code == 204
    assert _legs(client, headers, body["transfer_group_id"]) == []
    assert _balance(client, headers, a["id"]) == 100 and _balance(client, headers, b["id"]) == 10
    assert db_session.query(Transaction).filter(Transaction.is_transfer.is_(True)).count() == 0


def test_a_transfer_with_an_archived_account_can_still_be_deleted(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790110010")
    a, b, body = _make_transfer(client, headers)
    client.patch(f"/api/v1/accounts/{b['id']}", headers=headers, json={"is_active": False})
    assert client.delete(f"/api/v1/transactions/{body['in_transaction_id']}", headers=headers).status_code == 204
    assert _legs(client, headers, body["transfer_group_id"]) == []


def test_other_users_transfer_legs_are_untouchable(client, db_session):
    headers1, _ = register_with_persona(client, db_session, "0790110011")
    headers2, _ = register_with_persona(client, db_session, "0790110012")
    _, _, body = _make_transfer(client, headers1)
    url = f"/api/v1/transactions/{body['out_transaction_id']}"
    assert client.patch(url, headers=headers2, json={"amount": 1}).status_code == 404
    assert client.delete(url, headers=headers2).status_code == 404
    assert len(_legs(client, headers1, body["transfer_group_id"])) == 2


# ------------------------------------------------------------------ ربط المعاملة العادية بحساب

def test_quick_log_links_the_transaction_and_moves_the_balance(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790110013")
    account = _account(client, headers, "الكاش", 50)
    response = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 12, "type": "expense", "note": "قهوة", "account_id": account["id"], "occurred_at": _later(),
    })
    assert response.status_code == 201, response.text
    assert response.json()["account_id"] == account["id"]
    assert _balance(client, headers, account["id"]) == 38


def test_quick_log_rejects_foreign_and_archived_accounts(client, db_session):
    headers1, _ = register_with_persona(client, db_session, "0790110014")
    headers2, _ = register_with_persona(client, db_session, "0790110015")
    foreign = _account(client, headers2, "غريب", 5)
    archived = _account(client, headers1, "مؤرشف", 5)
    client.patch(f"/api/v1/accounts/{archived['id']}", headers=headers1, json={"is_active": False})

    def log(account_id):
        return client.post("/api/v1/transactions/quick-log", headers=headers1, json={
            "amount": 1, "type": "expense", "note": "x", "account_id": account_id})

    assert log(foreign["id"]).status_code == 404       # حقن account_id غريب
    assert log(archived["id"]).status_code == 400
    assert log(str(uuid.uuid4())).status_code == 404
    assert _transactions(client, headers1) == []


def test_patch_can_link_move_and_unlink_an_existing_transaction(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790110016")
    first, second = _account(client, headers, "أول", 100), _account(client, headers, "ثاني", 100)
    tx = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 10, "type": "expense", "note": "قديمة", "occurred_at": _later()}).json()
    url = f"/api/v1/transactions/{tx['id']}"

    assert _balance(client, headers, first["id"]) == 100                      # بدون حساب: ما إلها أثر
    assert client.patch(url, headers=headers, json={"account_id": first["id"]}).json()["account_id"] == first["id"]
    assert _balance(client, headers, first["id"]) == 90
    assert client.patch(url, headers=headers, json={"account_id": second["id"]}).status_code == 200  # نقل
    assert _balance(client, headers, first["id"]) == 100 and _balance(client, headers, second["id"]) == 90
    assert client.patch(url, headers=headers, json={"account_id": None}).json()["account_id"] is None  # فك الربط
    assert _balance(client, headers, second["id"]) == 100


def test_patch_account_rejects_foreign_and_archived_accounts_but_same_account_is_a_noop(client, db_session):
    headers1, _ = register_with_persona(client, db_session, "0790110017")
    headers2, _ = register_with_persona(client, db_session, "0790110018")
    mine = _account(client, headers1, "حسابي", 5)
    foreign = _account(client, headers2, "غريب", 5)
    archived = _account(client, headers1, "مؤرشف", 5)
    tx = client.post("/api/v1/transactions/quick-log", headers=headers1, json={
        "amount": 1, "type": "expense", "note": "x", "account_id": mine["id"]}).json()
    client.patch(f"/api/v1/accounts/{archived['id']}", headers=headers1, json={"is_active": False})
    url = f"/api/v1/transactions/{tx['id']}"

    assert client.patch(url, headers=headers1, json={"account_id": foreign["id"]}).status_code == 404
    assert client.patch(url, headers=headers1, json={"account_id": archived["id"]}).status_code == 400
    assert client.patch(url, headers=headers1, json={"account_id": mine["id"]}).status_code == 200


def test_account_in_use_cannot_be_deleted_until_its_transactions_are_gone(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790110019")
    account = _account(client, headers, "للحذف")  # بدون لقطة رصيد
    tx = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 1, "type": "expense", "note": "x", "account_id": account["id"]}).json()
    assert client.delete(f"/api/v1/accounts/{account['id']}", headers=headers).status_code == 409
    assert client.delete(f"/api/v1/transactions/{tx['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/accounts/{account['id']}", headers=headers).status_code == 204


# ------------------------------------------------------------------ قيود القاعدة (آخر خط دفاع)

def _raw_leg(user_id, account_id, kind, group_id, is_transfer=True):
    return Transaction(
        user_id=user_id, account_id=account_id, amount=Decimal("1"), type=kind, source=TransactionSource.MANUAL,
        occurred_at=_now(), is_transfer=is_transfer, transfer_group_id=group_id,
    )


def test_database_rejects_inconsistent_transfer_rows(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790110020")
    account = uuid.UUID(_account(client, headers, "قيود")["id"])
    group = uuid.uuid4()

    bad_rows = [
        _raw_leg(user.id, account, TransactionType.EXPENSE, None),                      # تحويل بدون مجموعة
        _raw_leg(user.id, None, TransactionType.EXPENSE, group),                        # تحويل بدون حساب
        _raw_leg(user.id, account, TransactionType.EXPENSE, group, is_transfer=False),  # معاملة عادية بمجموعة
    ]
    for row in bad_rows:
        db_session.add(row)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    db_session.add(_raw_leg(user.id, account, TransactionType.EXPENSE, group))
    db_session.commit()
    db_session.add(_raw_leg(user.id, account, TransactionType.EXPENSE, group))      # طرف خروج ثاني بنفس المجموعة
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ------------------------------------------------------------------ الاستثناء من الدخل والمصروف الحقيقي

def _add_expense(db_session, user, amount, days_ago):
    db_session.add(Transaction(
        user_id=user.id, amount=Decimal(str(amount)), type=TransactionType.EXPENSE, source=TransactionSource.MANUAL,
        occurred_at=_now() - timedelta(days=days_ago),
    ))
    db_session.commit()


def test_transfers_are_not_expenses_for_the_mood_engine(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790110021")
    a, b = _account(client, headers, "أ", 1000), _account(client, headers, "ب", 0)
    assert _transfer(client, headers, a["id"], b["id"], 500).status_code == 201
    _add_expense(db_session, user, 10, 1)

    db_session.expire_all()
    spent = mood_engine._sum_expenses(db_session, user, _now() - timedelta(days=7), _now() + timedelta(days=1))
    assert spent == 10.0


def test_transfers_are_not_expenses_for_the_essentials_estimate(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790110022")
    a, b = _account(client, headers, "أ", 1000), _account(client, headers, "ب", 0)
    _add_expense(db_session, user, 100, 20)    # بس لإثبات إنه في سجل أقدم من 14 يوم
    _add_expense(db_session, user, 14, 5)      # المصروف الحقيقي الوحيد بالنافذة
    assert _transfer(client, headers, a["id"], b["id"], 500, occurred_at=_iso(_now() - timedelta(days=3))).status_code == 201

    db_session.expire_all()
    estimate = financial_context.get_essentials_estimate(db_session, user)
    assert estimate.source == "history" and estimate.monthly_amount == 30.0  # (14 / 14) * 30 بدون الـ 500


def test_a_transfer_alone_is_not_enough_history_for_an_estimate(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790110023")
    a, b = _account(client, headers, "أ", 1000), _account(client, headers, "ب", 0)
    assert _transfer(client, headers, a["id"], b["id"], 500, occurred_at=_iso(_now() - timedelta(days=20))).status_code == 201

    db_session.expire_all()
    assert financial_context.get_essentials_estimate(db_session, user).source != "history"


def test_transfer_legs_never_get_category_suggestions(client, db_session, monkeypatch):
    headers, user = register_agent_user(client, db_session, "0790110024")
    food = Category(name="مطاعم", icon="utensils", is_default=True, category_type=CategoryType.EXPENSE)
    db_session.add(food)
    db_session.commit()
    patch_provider(monkeypatch, FakeJsonProvider(f'{{"category_id": "{food.id}", "reasoning": "x"}}'))

    a, b = _account(client, headers, "أ", 100), _account(client, headers, "ب", 0)
    assert _transfer(client, headers, a["id"], b["id"], 5, note="تحويل داخلي").status_code == 201
    assert client.post("/api/v1/agent/actions/check", headers=headers).json() == []  # ولا اقتراح لأطراف التحويل

    db_session.add(Transaction(  # الشاهد: معاملة عادية بدون تصنيف بنفس الظروف بتجيب اقتراح
        user_id=user.id, amount=5, type=TransactionType.EXPENSE, source=TransactionSource.MANUAL,
        note="سهرة مع الشباب", occurred_at=_now(),
    ))
    db_session.commit()
    actions = client.post("/api/v1/agent/actions/check", headers=headers).json()
    assert [a["action_type"] for a in actions] == ["suggest_category_correction"]


def test_a_transfer_is_not_a_logged_transaction_for_the_activation_metric(db_session):
    user = make_metrics_user(db_session, "0790199101", 1)
    first, second = (FinancialAccount(user_id=user.id, name=n, kind="cash") for n in ("أ", "ب"))
    db_session.add_all([first, second])
    db_session.flush()
    group = uuid.uuid4()
    for kind, account in ((TransactionType.EXPENSE, first), (TransactionType.INCOME, second)):
        leg = _raw_leg(user.id, account.id, kind, group)
        leg.created_at = user.created_at + timedelta(hours=2)
        db_session.add(leg)
    db_session.flush()

    def logged():
        report = usage_metrics_service.build_report(db_session, days=30, now=METRICS_NOW, exclude_phones=[])
        return report["funnel"]["logged_transaction"]

    assert logged() == 0
    add_metrics_transaction(db_session, user, 3)
    assert logged() == 1
