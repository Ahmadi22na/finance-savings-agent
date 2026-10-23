"""
الدفعة 0.E — تنبيه "ممكن مكرر": رسالة لصقها المستخدم يدويًا ثم ظهرت بالاستيراد.
تنبيه فقط (ما بيمنع الاستيراد، لأن تحويلين متطابقين فعليًا ممكن يكونوا حقيقيين).
"""
from tests.test_sms_import import RECEIVED, TRANSFER, get_auth_headers, msg


def _paste(client, headers, amount, type_, occurred_at, source="sms"):
    response = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": amount, "type": type_, "note": "رسالة ملصوقة", "source": source, "occurred_at": occurred_at,
    })
    assert response.status_code == 201, response.text


def _preview(client, headers, *messages):
    response = client.post("/api/v1/transactions/sms-import/preview", headers=headers, json={"messages": list(messages)})
    assert response.status_code == 200, response.text
    return response.json()["candidates"]


def test_pasted_message_is_flagged_when_it_shows_up_in_the_import(client, db_session):
    headers = get_auth_headers(client, "0790099001")
    _paste(client, headers, 4.5, "income", "2026-09-20T10:05:00Z")
    [candidate] = _preview(client, headers, msg(RECEIVED, "2026-09-20T10:00:00Z"))
    assert candidate["possible_duplicate"] is True and candidate["already_imported"] is False


def test_not_flagged_when_nothing_matches(client, db_session):
    headers = get_auth_headers(client, "0790099002")
    [candidate] = _preview(client, headers, msg(RECEIVED))
    assert candidate["possible_duplicate"] is False


def test_different_amount_type_or_far_time_are_not_flagged(client, db_session):
    headers = get_auth_headers(client, "0790099003")
    _paste(client, headers, 4.6, "income", "2026-09-20T10:05:00Z")      # مبلغ مختلف
    _paste(client, headers, 4.5, "expense", "2026-09-20T10:05:00Z")     # نوع مختلف
    _paste(client, headers, 4.5, "income", "2026-09-23T10:05:00Z")      # بعيد بالوقت
    [candidate] = _preview(client, headers, msg(RECEIVED, "2026-09-20T10:00:00Z"))
    assert candidate["possible_duplicate"] is False


def test_manual_entries_do_not_trigger_the_flag(client, db_session):
    headers = get_auth_headers(client, "0790099004")
    _paste(client, headers, 4.5, "income", "2026-09-20T10:05:00Z", source="manual")
    [candidate] = _preview(client, headers, msg(RECEIVED, "2026-09-20T10:00:00Z"))
    assert candidate["possible_duplicate"] is False


def test_one_pasted_transaction_flags_only_the_closest_of_two_identical_messages(client, db_session):
    headers = get_auth_headers(client, "0790099005")
    _paste(client, headers, 4.5, "income", "2026-09-20T10:05:00Z")
    candidates = _preview(client, headers, msg(RECEIVED, "2026-09-20T10:00:00Z"), msg(RECEIVED, "2026-09-20T18:00:00Z"))
    flagged = {c["received_at"][:16]: c["possible_duplicate"] for c in candidates}
    assert flagged == {"2026-09-20T10:00": True, "2026-09-20T18:00": False}


def test_imported_transactions_do_not_count_as_pasted(client, db_session):
    headers = get_auth_headers(client, "0790099006")
    assert client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json={
        "messages": [msg(RECEIVED, "2026-09-20T10:00:00Z")],
    }).status_code in (200, 201)
    [candidate] = _preview(client, headers, msg(RECEIVED, "2026-09-20T12:00:00Z"))
    assert candidate["possible_duplicate"] is False  # المستورد له بصمة، مش "ملصوق"


def test_already_imported_candidates_are_never_flagged(client, db_session):
    headers = get_auth_headers(client, "0790099007")
    _paste(client, headers, 4.5, "income", "2026-09-20T10:05:00Z")
    client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json={"messages": [msg(RECEIVED, "2026-09-20T10:00:00Z")]})
    [candidate] = _preview(client, headers, msg(RECEIVED, "2026-09-20T10:00:00Z"))
    assert candidate["already_imported"] is True and candidate["possible_duplicate"] is False


def test_other_users_pasted_transactions_never_flag_mine(client, db_session):
    headers1 = get_auth_headers(client, "0790099008")
    headers2 = get_auth_headers(client, "0790099009")
    _paste(client, headers1, 4.5, "income", "2026-09-20T10:05:00Z")
    [candidate] = _preview(client, headers2, msg(RECEIVED, "2026-09-20T10:00:00Z"))
    assert candidate["possible_duplicate"] is False


def test_flag_is_only_a_warning_confirm_still_imports(client, db_session):
    headers = get_auth_headers(client, "0790099010")
    _paste(client, headers, 4.5, "income", "2026-09-20T10:05:00Z")
    assert client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json={
        "messages": [msg(RECEIVED, "2026-09-20T10:00:00Z"), msg(TRANSFER, "2026-09-20T11:00:00Z")],
    }).status_code in (200, 201)
    assert len(client.get("/api/v1/transactions", headers=headers).json()) == 3  # الملصوقة + الاثنتين المستوردتين
