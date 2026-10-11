"""
R03 — خصوصية استيراد الرسائل: ما بنخزّن نص الرسالة، وبنتجاهل الرسائل غير ذات الصلة، ومنع التكرار شغّال.
"""
import logging

from app.models.transaction import Transaction, TransactionSource
from tests.test_income_and_goal_delete import register_with_persona

BANK_SMS = "Successfully received 4.500 JOD from 0791234567 Current balance JOD5,000.000 JOD."
PERSONAL_SMS = "يلا بنتقابل الساعة 8 عند القهوة، جيب معك 10 دنانير"


def messages(*bodies):
    return {"messages": [{"body": body, "received_at": "2026-10-06T14:41:00Z"} for body in bodies]}


def test_confirmed_import_does_not_store_the_sms_text(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790130001")

    response = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json=messages(BANK_SMS))

    assert response.status_code == 201
    stored = db_session.query(Transaction).filter(Transaction.user_id == user.id).one()
    assert stored.source == TransactionSource.SMS
    assert stored.raw_source_data is None
    assert stored.external_ref  # البصمة موجودة (منع التكرار)
    everything_stored = f"{stored.note} {stored.raw_source_data} {stored.external_ref}"
    assert "5,000" not in everything_stored and "Current balance" not in everything_stored  # الرصيد ما انحفظ


def test_deduplication_still_works_without_the_body(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790130002")
    first = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json=messages(BANK_SMS))
    second = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json=messages(BANK_SMS))
    assert len(first.json()) == 1 and second.json() == []
    assert db_session.query(Transaction).filter(Transaction.user_id == user.id).count() == 1


def test_non_bank_messages_are_ignored_and_nothing_is_stored(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790130003")

    preview = client.post("/api/v1/transactions/sms-import/preview", headers=headers, json=messages(PERSONAL_SMS, BANK_SMS))
    assert [c["amount"] for c in preview.json()["candidates"]] == [4.5]
    assert db_session.query(Transaction).filter(Transaction.user_id == user.id).count() == 0  # المعاينة ما بتحفظ شي

    only_personal = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json=messages(PERSONAL_SMS))
    assert only_personal.json() == []
    assert db_session.query(Transaction).filter(Transaction.user_id == user.id).count() == 0


def test_sms_text_never_reaches_the_logs(client, db_session, caplog):
    headers, _ = register_with_persona(client, db_session, "0790130004")
    with caplog.at_level(logging.DEBUG):
        client.post("/api/v1/transactions/sms-import/preview", headers=headers, json=messages(PERSONAL_SMS, BANK_SMS))
        client.post("/api/v1/transactions/parse-sms", headers=headers, json={"text": BANK_SMS})
    assert "5,000" not in caplog.text and "بنتقابل" not in caplog.text and "0791234567" not in caplog.text
