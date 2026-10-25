"""
المرحلة 1 / الدفعة 1.A — الحسابات المالية اليدوية ولقطات الرصيد وحساب الرصيد.
تشتغل على SQLite وPostgreSQL (التزامن الحقيقي بـ tests/pg/test_pg_financial_accounts.py).
المعاملات المرتبطة بحساب بتنكتب هون مباشرة بالقاعدة، لأن ربطها عبر الـ API بالدفعة 1.B.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.financial_account import AccountBalanceSnapshot, FinancialAccount
from app.models.transaction import Transaction, TransactionSource, TransactionType
from tests.test_income_and_goal_delete import register_with_persona

NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _create(client, headers, name="الكاش", kind="cash", **extra):
    response = client.post("/api/v1/accounts", headers=headers, json={"name": name, "kind": kind, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _snapshot(client, headers, account_id, amount, as_of=None):
    body = {"amount": amount}
    if as_of is not None:
        body["as_of"] = _iso(as_of)
    response = client.post(f"/api/v1/accounts/{account_id}/balance", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _tx(db_session, user, account_id, amount, type_, occurred_at, created_at=None):
    row = Transaction(
        user_id=user.id, account_id=uuid.UUID(account_id) if account_id else None, amount=Decimal(str(amount)),
        type=type_, source=TransactionSource.MANUAL, occurred_at=occurred_at,
    )
    if created_at is not None:
        row.created_at = created_at
    db_session.add(row)
    db_session.commit()
    return row


def _account(client, headers, account_id):
    response = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------ الإنشاء والتحقق

def test_create_with_opening_balance_is_manual_confirmed(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790100001")
    account = _create(client, headers, opening_balance=35.5)
    assert account["balance"] == 35.5 and account["balance_quality"] == "manual_confirmed"
    assert account["currency"] == "JOD" and account["is_active"] is True
    assert account["transactions_since_snapshot"] == 0 and account["ignored_before_snapshot"] == 0


def test_account_without_snapshot_has_unknown_balance_not_zero(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790100002")
    account = _create(client, headers)
    assert account["balance"] is None and account["balance_quality"] == "unknown"
    assert account["balance_as_of"] is None and account["last_snapshot_amount"] is None


def test_negative_balances_are_allowed(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790100003")
    account = _create(client, headers, "مكشوف", "bank", opening_balance=-120.5)
    assert account["balance"] == -120.5
    assert _snapshot(client, headers, account["id"], -3)["balance"] == -3


@pytest.mark.parametrize("body", [
    {"name": "x", "kind": "crypto"},
    {"name": "   ", "kind": "cash"},
    {"name": "", "kind": "cash"},
    {"name": "x" * 61, "kind": "cash"},
    {"name": "x", "kind": "cash", "opening_balance": 1.0001},
    {"name": "x", "kind": "cash", "opening_balance": "abc"},
])
def test_create_validation(client, db_session, body):
    headers, _ = register_with_persona(client, db_session, "0790100004")
    assert client.post("/api/v1/accounts", headers=headers, json=body).status_code == 422


def test_name_is_unique_per_user_ignoring_case_and_extra_spaces(client, db_session):
    headers1, _ = register_with_persona(client, db_session, "0790100005")
    headers2, _ = register_with_persona(client, db_session, "0790100006")
    _create(client, headers1, "My Wallet", "wallet")
    for duplicate in ("my wallet", "MY WALLET", "  My   Wallet  "):
        response = client.post("/api/v1/accounts", headers=headers1, json={"name": duplicate, "kind": "bank"})
        assert response.status_code == 409, duplicate
    assert client.post("/api/v1/accounts", headers=headers2, json={"name": "my wallet", "kind": "wallet"}).status_code == 201
    assert db_session.query(FinancialAccount).count() == 2  # الفرادة مفروضة بالقاعدة (واحد لكل مستخدم)


def test_rename_conflict_and_validation(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790100007")
    first, second = _create(client, headers, "أول"), _create(client, headers, "ثاني")
    url = f"/api/v1/accounts/{second['id']}"
    assert client.patch(url, headers=headers, json={"name": "أول"}).status_code == 409
    assert client.patch(url, headers=headers, json={}).status_code == 422
    assert client.patch(url, headers=headers, json={"name": None}).status_code == 422
    assert client.patch(url, headers=headers, json={"kind": "crypto"}).status_code == 422
    assert client.patch(url, headers=headers, json={"name": "جديد", "kind": "wallet"}).json()["name"] == "جديد"
    assert first["name"] == "أول"


# ------------------------------------------------------------------ العزل

def test_other_users_accounts_are_invisible_and_untouchable(client, db_session):
    headers1, _ = register_with_persona(client, db_session, "0790100008")
    headers2, _ = register_with_persona(client, db_session, "0790100009")
    account = _create(client, headers1, opening_balance=10)
    url = f"/api/v1/accounts/{account['id']}"

    assert client.get(url, headers=headers2).status_code == 404
    assert client.patch(url, headers=headers2, json={"name": "سرقة"}).status_code == 404
    assert client.delete(url, headers=headers2).status_code == 404
    assert client.post(url + "/balance", headers=headers2, json={"amount": 1}).status_code == 404
    assert client.get(url + "/snapshots", headers=headers2).status_code == 404
    assert client.get("/api/v1/accounts", headers=headers2).json() == []
    assert client.get("/api/v1/accounts/summary", headers=headers2).json()["accounts_total"] == 0


def test_accounts_require_authentication(client, db_session):
    assert client.get("/api/v1/accounts").status_code == 401
    assert client.post("/api/v1/accounts", json={"name": "x", "kind": "cash"}).status_code == 401


# ------------------------------------------------------------------ قواعد الرصيد

def test_balance_is_anchor_plus_signed_movements_with_three_decimals(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790100010")
    account = _create(client, headers)
    anchor = NOW - timedelta(days=2)
    _snapshot(client, headers, account["id"], 100, anchor)
    _tx(db_session, user, account["id"], "10.125", TransactionType.INCOME, anchor + timedelta(hours=1))
    _tx(db_session, user, account["id"], "3.5", TransactionType.EXPENSE, anchor + timedelta(hours=2))

    result = _account(client, headers, account["id"])
    assert result["balance"] == 106.625 and result["balance_quality"] == "derived"
    assert result["transactions_since_snapshot"] == 2 and result["last_snapshot_amount"] == 100


def test_transaction_exactly_at_snapshot_time_is_not_counted(client, db_session):
    """تساوي التوقيت: وقت المعاملة = وقت اللقطة → ما بتنحسب (اللقطة شاملة لها). بعدها بثانية → بتنحسب."""
    headers, user = register_with_persona(client, db_session, "0790100011")
    account = _create(client, headers)
    anchor = NOW - timedelta(days=3)
    _snapshot(client, headers, account["id"], 50, anchor)
    _tx(db_session, user, account["id"], 10, TransactionType.EXPENSE, anchor)
    assert _account(client, headers, account["id"])["balance"] == 50

    _tx(db_session, user, account["id"], 10, TransactionType.EXPENSE, anchor + timedelta(seconds=1))
    result = _account(client, headers, account["id"])
    assert result["balance"] == 40 and result["transactions_since_snapshot"] == 1


def test_backdated_transaction_entered_after_the_snapshot_is_ignored_and_reported(client, db_session):
    """معاملة بتاريخ قديم (قبل اللقطة) سُجّلت بعدها: ما بتغيّر الرصيد، وبنكشفها بـ ignored_before_snapshot."""
    headers, user = register_with_persona(client, db_session, "0790100012")
    account = _create(client, headers)
    anchor = NOW - timedelta(days=3)
    _snapshot(client, headers, account["id"], 80, anchor)
    _tx(db_session, user, account["id"], 25, TransactionType.EXPENSE, anchor - timedelta(days=1),
        created_at=datetime.now(timezone.utc) + timedelta(minutes=1))  # سُجّلت بعد اللقطة بتاريخ أقدم منها
    _tx(db_session, user, account["id"], 7, TransactionType.EXPENSE, anchor,  # يساوي وقت اللقطة، سُجّلت بعدها
        created_at=datetime.now(timezone.utc) + timedelta(minutes=1))

    result = _account(client, headers, account["id"])
    assert result["balance"] == 80 and result["balance_quality"] == "manual_confirmed"
    assert result["transactions_since_snapshot"] == 0 and result["ignored_before_snapshot"] == 2


def test_transaction_older_than_the_snapshot_and_entered_before_it_is_not_reported_as_ignored(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790100013")
    account = _create(client, headers)
    anchor = NOW - timedelta(days=3)
    _tx(db_session, user, account["id"], 25, TransactionType.EXPENSE, anchor - timedelta(days=1),
        created_at=datetime.now(timezone.utc) - timedelta(days=5))  # سُجّلت قبل اللقطة أصلاً: عادي
    _snapshot(client, headers, account["id"], 80, anchor)
    result = _account(client, headers, account["id"])
    assert result["balance"] == 80 and result["ignored_before_snapshot"] == 0


def test_unlinked_and_other_account_transactions_have_no_effect(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790100014")
    account, other = _create(client, headers, "أول"), _create(client, headers, "ثاني")
    anchor = NOW - timedelta(days=2)
    _snapshot(client, headers, account["id"], 100, anchor)
    _tx(db_session, user, None, 40, TransactionType.EXPENSE, anchor + timedelta(hours=1))           # بدون حساب
    _tx(db_session, user, other["id"], 40, TransactionType.EXPENSE, anchor + timedelta(hours=1))   # حساب ثاني
    result = _account(client, headers, account["id"])
    assert result["balance"] == 100 and result["transactions_since_snapshot"] == 0


def test_a_newer_snapshot_becomes_the_anchor_and_old_movements_stop_counting(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790100015")
    account = _create(client, headers)
    first = NOW - timedelta(days=5)
    _snapshot(client, headers, account["id"], 100, first)
    _tx(db_session, user, account["id"], 30, TransactionType.EXPENSE, first + timedelta(days=1))
    assert _account(client, headers, account["id"])["balance"] == 70

    _snapshot(client, headers, account["id"], 64, first + timedelta(days=2))  # المستخدم صحّح رصيده
    result = _account(client, headers, account["id"])
    assert result["balance"] == 64 and result["transactions_since_snapshot"] == 0
    history = client.get(f"/api/v1/accounts/{account['id']}/snapshots", headers=headers).json()
    assert [row["amount"] for row in history] == [64, 100]  # الأحدث أولاً، والقديمة تبقى للمراجعة


def test_stale_snapshot_is_flagged_but_balance_is_still_computed(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790100016")
    account = _create(client, headers)
    old = NOW - timedelta(days=40)
    _snapshot(client, headers, account["id"], 100, old)
    _tx(db_session, user, account["id"], 10, TransactionType.INCOME, old + timedelta(days=1))
    result = _account(client, headers, account["id"])
    assert result["balance_quality"] == "stale" and result["balance"] == 110


def test_snapshot_in_the_future_is_rejected(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790100017")
    account = _create(client, headers)
    response = client.post(f"/api/v1/accounts/{account['id']}/balance", headers=headers,
                           json={"amount": 5, "as_of": _iso(NOW + timedelta(days=1))})
    assert response.status_code == 400


def test_summary_counts_only_known_balances_and_flags_incomplete(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790100018")
    _create(client, headers, "أ", opening_balance=100)
    _create(client, headers, "ب", "bank", opening_balance=-30.5)
    unknown = _create(client, headers, "ج", "wallet")
    archived = _create(client, headers, "مؤرشف", opening_balance=999)
    client.patch(f"/api/v1/accounts/{archived['id']}", headers=headers, json={"is_active": False})

    summary = client.get("/api/v1/accounts/summary", headers=headers).json()
    assert summary["total"] == 69.5 and summary["accounts_total"] == 3 and summary["accounts_counted"] == 2
    assert summary["has_unknown"] is True and summary["incomplete"] is True

    _snapshot(client, headers, unknown["id"], 0.5)
    summary = client.get("/api/v1/accounts/summary", headers=headers).json()
    assert summary["total"] == 70 and summary["has_unknown"] is False and summary["incomplete"] is False


def test_summary_with_no_accounts(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790100019")
    summary = client.get("/api/v1/accounts/summary", headers=headers).json()
    assert summary == {"total": None, "accounts_total": 0, "accounts_counted": 0,
                       "has_unknown": False, "has_stale": False, "incomplete": False}


# ------------------------------------------------------------------ الحذف والأرشفة

def test_empty_account_can_be_deleted(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790100020")
    account = _create(client, headers)
    assert client.delete(f"/api/v1/accounts/{account['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/accounts/{account['id']}", headers=headers).status_code == 404


def test_account_with_a_snapshot_or_a_transaction_cannot_be_deleted(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790100021")
    with_snapshot = _create(client, headers, "بلقطة", opening_balance=5)
    with_tx = _create(client, headers, "بمعاملة")
    _tx(db_session, user, with_tx["id"], 1, TransactionType.EXPENSE, NOW)

    assert client.delete(f"/api/v1/accounts/{with_snapshot['id']}", headers=headers).status_code == 409
    assert client.delete(f"/api/v1/accounts/{with_tx['id']}", headers=headers).status_code == 409
    assert db_session.query(AccountBalanceSnapshot).count() == 1  # ما انحذف شي


def test_archived_account_keeps_its_history_but_accepts_no_new_snapshots(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790100022")
    account = _create(client, headers, opening_balance=20)
    _tx(db_session, user, account["id"], 5, TransactionType.EXPENSE, NOW + timedelta(seconds=-1))
    url = f"/api/v1/accounts/{account['id']}"

    assert client.patch(url, headers=headers, json={"is_active": False}).json()["is_active"] is False
    assert all(a["id"] != account["id"] for a in client.get("/api/v1/accounts", headers=headers).json())
    archived_list = client.get("/api/v1/accounts?include_archived=true", headers=headers).json()
    assert any(a["id"] == account["id"] for a in archived_list)
    assert client.get(url, headers=headers).json()["last_snapshot_amount"] == 20      # الرصيد قابل للمراجعة
    assert len(client.get(url + "/snapshots", headers=headers).json()) == 1          # واللقطات
    assert client.post(url + "/balance", headers=headers, json={"amount": 1}).status_code == 400

    assert client.patch(url, headers=headers, json={"is_active": True}).json()["is_active"] is True
    assert client.post(url + "/balance", headers=headers, json={"amount": 1}).status_code == 201


def test_deleting_the_user_removes_accounts_snapshots_and_linked_transactions(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790100023")
    account = _create(client, headers, opening_balance=10)
    _tx(db_session, user, account["id"], 2, TransactionType.EXPENSE, NOW)
    response = client.request("DELETE", "/api/v1/users/me", headers=headers, json={"password": "testpassword123", "confirm": True})
    assert response.status_code == 204, response.text
    db_session.expire_all()
    assert db_session.query(FinancialAccount).count() == 0
    assert db_session.query(AccountBalanceSnapshot).count() == 0
