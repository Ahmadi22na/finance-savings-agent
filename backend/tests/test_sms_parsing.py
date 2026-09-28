"""اختبارات تحليل رسائل CliQ البنكية (Sprint 9 — SMS Parsing، نمط Copy-Paste)."""
import pytest


def get_auth_headers(client, phone="0790030001"):
    response = client.post("/api/v1/auth/register", json={
        "name": "مستخدم اختبار", "phone": phone, "password": "testpassword123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_parse_sms_recognizes_cliq_received_message(client, db_session):
    """نص حقيقي بالضبط زي ما بعته أحمد."""
    headers = get_auth_headers(client)
    text = "Successfully received 4.500 JOD from 00962781330482 Current balance JOD4.760 JOD."

    response = client.post("/api/v1/transactions/parse-sms", headers=headers, json={"text": text})
    assert response.status_code == 200
    body = response.json()

    assert body["parsed"] is True
    assert body["amount"] == 4.5
    assert body["type"] == "income"
    assert "00962781330482" in body["note"]


def test_parse_sms_recognizes_cliq_transfer_message(client, db_session):
    headers = get_auth_headers(client)
    text = "Successful transfer of JOD6.000 to OSAMAH222 Current balance JOD00.260."

    response = client.post("/api/v1/transactions/parse-sms", headers=headers, json={"text": text})
    assert response.status_code == 200
    body = response.json()

    assert body["parsed"] is True
    assert body["amount"] == 6.0
    assert body["type"] == "expense"
    assert "OSAMAH222" in body["note"]


def test_parse_sms_handles_unrecognized_text(client, db_session):
    """رسالة/نص مش من نمط مدعوم — لازم يرجّع parsed=False، مش يخترع أرقام."""
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/parse-sms", headers=headers, json={
        "text": "هلا كيفك شو أخبارك اليوم؟",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["parsed"] is False
    assert body["amount"] is None


def test_parse_sms_handles_amount_with_thousands_separator(client, db_session):
    """مبلغ فيه فاصلة آلاف (زي 1,250.500) — لازم يتحول لرقم صح."""
    headers = get_auth_headers(client)
    text = "Successfully received 1,250.500 JOD from 0791234567 Current balance JOD5,000.000 JOD."

    response = client.post("/api/v1/transactions/parse-sms", headers=headers, json={"text": text})
    assert response.status_code == 200
    body = response.json()
    assert body["parsed"] is True
    assert body["amount"] == 1250.5


def test_parse_sms_never_creates_a_transaction(client, db_session):
    """أهم قرار تصميم بهالميزة، نفس OCR بالظبط: التحليل لحاله ما لازم ينشئ معاملة."""
    headers = get_auth_headers(client)
    client.post("/api/v1/transactions/parse-sms", headers=headers, json={
        "text": "Successfully received 4.500 JOD from 00962781330482 Current balance JOD4.760 JOD.",
    })

    transactions = client.get("/api/v1/transactions", headers=headers).json()
    assert transactions == []


def test_parse_sms_rejects_too_short_text(client, db_session):
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/parse-sms", headers=headers, json={"text": "ok"})
    assert response.status_code == 422  # min_length=3 بالـ schema
