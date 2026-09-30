"""اختبارات استيراد رسائل CliQ من صندوق الوارد (Sprint 9 — المرحلة 1)."""

RECEIVED = "Successfully received 4.500 JOD from 00962781330482 Current balance JOD4.760 JOD."
TRANSFER = "Successful transfer of JOD6.000 to OSAMAH222 Current balance JOD00.260."
JUNK = "هلا شو أخبارك؟ شفتك مبارح"


def get_auth_headers(client, phone="0790040001"):
    response = client.post("/api/v1/auth/register", json={
        "name": "مستخدم اختبار", "phone": phone, "password": "testpassword123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def msg(body, received_at="2026-09-20T10:00:00Z"):
    return {"body": body, "received_at": received_at}


def test_preview_returns_only_parseable_messages(client, db_session):
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/sms-import/preview", headers=headers, json={
        "messages": [msg(RECEIVED), msg(JUNK), msg(TRANSFER, "2026-09-21T09:00:00Z")],
    })
    assert response.status_code == 200
    candidates = response.json()["candidates"]

    assert len(candidates) == 2
    assert all(c["already_imported"] is False for c in candidates)
    # الأحدث أول
    assert candidates[0]["type"] == "expense" and candidates[0]["amount"] == 6.0
    assert candidates[1]["type"] == "income" and candidates[1]["amount"] == 4.5


def test_preview_never_creates_transactions(client, db_session):
    headers = get_auth_headers(client)
    client.post("/api/v1/transactions/sms-import/preview", headers=headers, json={
        "messages": [msg(RECEIVED)],
    })
    assert client.get("/api/v1/transactions", headers=headers).json() == []


def test_confirm_creates_sms_transactions_with_server_side_values(client, db_session):
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json={
        "messages": [msg(RECEIVED, "2026-09-20T10:00:00Z"), msg(TRANSFER, "2026-09-21T09:00:00Z")],
    })
    assert response.status_code == 201
    created = response.json()
    assert len(created) == 2

    by_type = {t["type"]: t for t in created}
    assert by_type["income"]["amount"] == 4.5
    assert by_type["income"]["source"] == "sms"
    assert by_type["income"]["occurred_at"].startswith("2026-09-20T10:00:00")
    # الدخل المستورد لسا ما اتوزع على أي خطة — الموبايل يستخدمها ليسأل المستخدم
    assert by_type["income"]["unallocated_amount"] == 4.5
    assert by_type["expense"]["amount"] == 6.0
    assert by_type["expense"]["unallocated_amount"] == 0


def test_confirm_twice_does_not_duplicate(client, db_session):
    headers = get_auth_headers(client)
    payload = {"messages": [msg(RECEIVED), msg(TRANSFER, "2026-09-21T09:00:00Z")]}

    first = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json=payload)
    second = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json=payload)

    assert len(first.json()) == 2
    assert second.status_code == 201
    assert second.json() == []
    assert len(client.get("/api/v1/transactions", headers=headers).json()) == 2


def test_preview_flags_already_imported_messages(client, db_session):
    headers = get_auth_headers(client)
    client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json={
        "messages": [msg(RECEIVED)],
    })
    response = client.post("/api/v1/transactions/sms-import/preview", headers=headers, json={
        "messages": [msg(RECEIVED), msg(TRANSFER, "2026-09-21T09:00:00Z")],
    })
    flags = {c["type"]: c["already_imported"] for c in response.json()["candidates"]}
    assert flags == {"income": True, "expense": False}


def test_same_text_at_different_times_are_distinct_transactions(client, db_session):
    """تحويلين متطابقين تمامًا (نفس المبلغ ونفس المستلم) بوقتين مختلفين
    لازم ينستوردوا كمعاملتين — مش تكرار."""
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json={
        "messages": [msg(TRANSFER, "2026-09-21T09:00:00Z"), msg(TRANSFER, "2026-09-22T09:00:00Z")],
    })
    assert len(response.json()) == 2


def test_identical_message_repeated_in_one_request_imported_once(client, db_session):
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json={
        "messages": [msg(RECEIVED), msg(RECEIVED)],
    })
    assert len(response.json()) == 1


def test_confirm_ignores_unparseable_messages(client, db_session):
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json={
        "messages": [msg(JUNK)],
    })
    assert response.status_code == 201
    assert response.json() == []
    assert client.get("/api/v1/transactions", headers=headers).json() == []


def test_dedup_is_scoped_per_user(client, db_session):
    """مستخدم ثاني بيوصله نفس نص الرسالة بنفس الوقت — لازم يقدر يستوردها."""
    headers1 = get_auth_headers(client, "0790040002")
    headers2 = get_auth_headers(client, "0790040003")

    first = client.post("/api/v1/transactions/sms-import/confirm", headers=headers1, json={
        "messages": [msg(RECEIVED)],
    })
    second = client.post("/api/v1/transactions/sms-import/confirm", headers=headers2, json={
        "messages": [msg(RECEIVED)],
    })
    assert len(first.json()) == 1
    assert len(second.json()) == 1


def test_too_many_messages_rejected(client, db_session):
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/sms-import/preview", headers=headers, json={
        "messages": [msg(RECEIVED, f"2026-09-20T10:{i % 60:02d}:00Z") for i in range(301)],
    })
    assert response.status_code == 422


def test_sms_import_requires_auth(client, db_session):
    response = client.post("/api/v1/transactions/sms-import/preview", json={"messages": [msg(RECEIVED)]})
    assert response.status_code in (401, 403)


def test_concurrent_duplicate_hits_db_constraint_and_returns_409(client, db_session, monkeypatch):
    """
    لو طلبين متزامنين عدّوا فحص "موجود قبل؟" سوا، قيد UNIQUE بقاعدة البيانات
    هو خط الدفاع الأخير — لازم يرجّع 409 واضح ومش يخرّب البيانات أو يرمي 500.
    نحاكيه بإجبار فحص الموجود يرجّع فاضي.
    """
    from app.services import sms_import_service

    headers = get_auth_headers(client)
    client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json={
        "messages": [msg(RECEIVED)],
    })

    monkeypatch.setattr(sms_import_service, "_existing_refs", lambda db, user, refs: set())
    response = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json={
        "messages": [msg(RECEIVED)],
    })
    assert response.status_code == 409

    monkeypatch.undo()
    assert len(client.get("/api/v1/transactions", headers=headers).json()) == 1
