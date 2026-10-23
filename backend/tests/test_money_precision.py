"""
الدفعة 0.B — دقة 3 خانات (فلس) و Decimal بالحسابات المالية.
تشتغل على SQLite وPostgreSQL. (اختبارات الدقة على مستوى القاعدة بـ tests/pg/.)
"""
from decimal import Decimal

import pytest
from pydantic import BaseModel, Field, ValidationError

from app.core.money import MoneyIn, to_money
from app.services import sms_parser_service
from tests.test_income_and_goal_delete import register_with_persona


class _Probe(BaseModel):
    amount: MoneyIn = Field(gt=0, max_digits=14, decimal_places=3)


# ---------- وحدات (بدون قاعدة بيانات) ----------

def test_to_money_rounds_half_up_to_three_decimals():
    assert to_money(2.675) == Decimal("2.675")
    assert to_money(Decimal("0.0005")) == Decimal("0.001")
    assert to_money(Decimal("0.0004")) == Decimal("0.000")
    assert to_money(5) == Decimal("5.000")


def test_to_money_does_not_inherit_binary_float_error():
    assert to_money(0.1) + to_money(0.2) == Decimal("0.300")


@pytest.mark.parametrize("raw", [4.5, 4.505, 33.33, 10, "1.250", Decimal("2.5")])
def test_money_input_accepts_up_to_three_decimals(raw):
    assert _Probe(amount=raw).amount == Decimal(str(raw))


def test_money_input_tolerates_float_noise():
    assert _Probe(amount=0.1 + 0.2).amount == Decimal("0.300")


@pytest.mark.parametrize("bad", [0, -5, 10.0004, 0.0004, float("nan"), float("inf"), 1e15, "abc"])
def test_money_input_rejects_invalid(bad):
    with pytest.raises(ValidationError):
        _Probe(amount=bad)


def test_sms_parser_returns_exact_decimal():
    parsed = sms_parser_service.parse_sms("Successfully received 12.345 JOD from 0791234567 Current balance JOD5,000.000 JOD.")
    assert parsed.amount == Decimal("12.345")
    parsed = sms_parser_service.parse_sms("Successfully received 1,250.500 JOD from 0791234567")
    assert parsed.amount == Decimal("1250.500")


# ---------- عبر الـ API ----------

def _quick_log(client, headers, amount, type_="expense"):
    return client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": amount, "type": type_, "note": "اختبار دقة",
    })


def test_quick_log_keeps_three_decimals(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790095001")
    response = _quick_log(client, headers, 4.505)
    assert response.status_code == 201
    assert response.json()["amount"] == 4.505
    listed = client.get("/api/v1/transactions", headers=headers).json()
    assert any(t["amount"] == 4.505 for t in listed)


def test_quick_log_rejects_sub_fils_amount(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790095002")
    assert _quick_log(client, headers, 4.5005).status_code == 422


def test_quick_log_accepts_client_float_noise(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790095003")
    response = _quick_log(client, headers, 0.1 + 0.2)
    assert response.status_code == 201
    assert response.json()["amount"] == 0.3


def test_goal_with_three_decimal_target_and_fils_contribution(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790095004")
    goal = client.post("/api/v1/goals", headers=headers, json={"title": "دقة", "target_amount": 1000.125}).json()
    assert goal["target_amount"] == 1000.125
    after = client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 0.001}).json()
    assert after["current_amount"] == 0.001


def test_contribution_sum_has_no_float_drift(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790095005")
    goal = client.post("/api/v1/goals", headers=headers, json={"title": "مجموع", "target_amount": 1000}).json()
    for _ in range(10):
        response = client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 0.1})
        assert response.status_code == 200
    assert response.json()["current_amount"] == 1.0


def test_contribute_rejects_sub_fils_amount(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790095006")
    goal = client.post("/api/v1/goals", headers=headers, json={"title": "رفض", "target_amount": 100}).json()
    response = client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 1.0001})
    assert response.status_code == 422


def test_parse_sms_endpoint_returns_three_decimal_amount(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790095007")
    response = client.post("/api/v1/transactions/parse-sms", headers=headers, json={
        "text": "Successfully received 12.345 JOD from 0791234567 Current balance JOD5,000.000 JOD.",
    })
    assert response.status_code == 200
    assert response.json()["amount"] == 12.345
