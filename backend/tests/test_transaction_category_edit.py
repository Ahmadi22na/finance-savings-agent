"""
R01 — مصدر المعاملة ودرجة التأكد: شارات واضحة (يدوي/مستورد/تصنيف تلقائي) وتعديل التصنيف وحفظه.
"""
from datetime import datetime, timezone

from app.models.agent import AgentAction, AgentActionStatus, AgentActionType
from app.models.category import Category, CategoryType
from app.models.transaction import Transaction, TransactionSource, TransactionType
from tests.test_income_and_goal_delete import register_with_persona

BANK_SMS = "Successfully received 4.500 JOD from 0791234567 Current balance JOD5,000.000 JOD."


def make_category(db_session, name, kind=CategoryType.EXPENSE, keywords=None, user_id=None):
    category = Category(
        name=name, icon="tag", is_default=user_id is None, category_type=kind, keywords=keywords or [], user_id=user_id,
    )
    db_session.add(category)
    db_session.commit()
    return category


def quick_log(client, headers, **body):
    payload = {"amount": 5, "type": "expense"}
    payload.update(body)
    return client.post("/api/v1/transactions/quick-log", headers=headers, json=payload)


def patch(client, headers, transaction_id, category_id):
    return client.patch(f"/api/v1/transactions/{transaction_id}", headers=headers, json={"category_id": category_id})


def listed(client, headers, transaction_id):
    return next(t for t in client.get("/api/v1/transactions", headers=headers).json() if t["id"] == transaction_id)


# ----------------------------------------------------------- مصدر التصنيف وقت الإنشاء

def test_icon_path_marks_the_category_as_chosen_by_the_user(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790160001")
    food = make_category(db_session, "مطاعم")

    created = quick_log(client, headers, category_id=str(food.id)).json()

    assert created["category_origin"] == "user" and created["category_confidence"] is None
    assert created["ai_suggested"] is False


def test_text_path_marks_auto_with_confidence_and_it_survives_in_the_list(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790160002")
    make_category(db_session, "مطاعم", keywords=["مطعم"])

    created = quick_log(client, headers, note="غدا بمطعم الحارة").json()
    from_list = listed(client, headers, created["id"])

    assert created["category_origin"] == "auto" and created["ai_suggested"] is True
    for item in (created, from_list):
        assert 0 < item["category_confidence"] <= 1
        assert item["category"]["name"] == "مطاعم"
    # ما كان ممكن نعرضها بالقائمة قبل: ai_suggested كان يرجع false دايمًا هناك
    assert from_list["ai_suggested"] is True
    assert from_list["suggestion_confidence"] == from_list["category_confidence"]


def test_unmatched_note_stays_uncategorized_without_origin(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790160003")
    make_category(db_session, "مطاعم", keywords=["مطعم"])

    created = quick_log(client, headers, note="شي ما إله علاقة").json()

    assert created["category"] is None
    assert created["category_origin"] is None and created["ai_suggested"] is False


def test_source_label_is_stored_and_validated(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790160004")
    assert quick_log(client, headers, note="فاتورة", source="ocr").json()["source"] == "ocr"
    assert quick_log(client, headers, note="رسالة", source="sms").json()["source"] == "sms"
    assert quick_log(client, headers, note="عادي").json()["source"] == "manual"
    assert quick_log(client, headers, note="x", source="open_banking").status_code == 422


def test_quick_log_rejects_unknown_or_foreign_categories(client, db_session):
    headers_a, _ = register_with_persona(client, db_session, "0790160005")
    _, user_b = register_with_persona(client, db_session, "0790160006")
    foreign = make_category(db_session, "تصنيف غيري", user_id=user_b.id)

    unknown = quick_log(client, headers_a, category_id="3fa85f64-5717-4562-b3fc-2c963f66afa6")
    stolen = quick_log(client, headers_a, category_id=str(foreign.id))

    assert unknown.status_code == 400 and stolen.status_code == 400
    assert db_session.query(Transaction).count() == 0


# --------------------------------------------------------------------- تعديل التصنيف

def test_editing_the_category_replaces_the_auto_badge_with_user_ownership(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790160007")
    make_category(db_session, "مطاعم", keywords=["مطعم"])
    entertainment = make_category(db_session, "ترفيه")
    created = quick_log(client, headers, note="غدا بمطعم").json()
    assert created["category_origin"] == "auto"

    response = patch(client, headers, created["id"], str(entertainment.id))

    assert response.status_code == 200
    body = response.json()
    assert body["category"]["name"] == "ترفيه"
    assert body["category_origin"] == "user" and body["category_confidence"] is None
    assert body["ai_suggested"] is False and body["suggestion_confidence"] is None
    saved = listed(client, headers, created["id"])  # انحفظ فعلًا
    assert saved["category"]["name"] == "ترفيه" and saved["category_origin"] == "user"


def test_null_category_removes_it(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790160008")
    food = make_category(db_session, "مطاعم")
    created = quick_log(client, headers, category_id=str(food.id)).json()

    body = patch(client, headers, created["id"], None).json()

    assert body["category"] is None and body["category_origin"] is None


def test_category_must_fit_the_transaction_type(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790160009")
    salary = make_category(db_session, "راتب", kind=CategoryType.INCOME)
    anything = make_category(db_session, "متفرقات", kind=CategoryType.BOTH)
    expense = quick_log(client, headers, note="قهوة").json()

    assert patch(client, headers, expense["id"], str(salary.id)).status_code == 400
    assert patch(client, headers, expense["id"], str(anything.id)).status_code == 200


def test_cannot_edit_someone_elses_transaction_or_use_their_category(client, db_session):
    headers_a, _ = register_with_persona(client, db_session, "0790160010")
    headers_b, user_b = register_with_persona(client, db_session, "0790160011")
    mine = make_category(db_session, "تصنيفي")
    foreign = make_category(db_session, "تصنيف غيري", user_id=user_b.id)
    tx_a = quick_log(client, headers_a, category_id=str(mine.id)).json()

    assert patch(client, headers_b, tx_a["id"], str(mine.id)).status_code == 404  # معاملة مستخدم ثاني
    assert patch(client, headers_a, tx_a["id"], str(foreign.id)).status_code == 400
    assert patch(client, headers_a, tx_a["id"], "3fa85f64-5717-4562-b3fc-2c963f66afa6").status_code == 400
    assert listed(client, headers_a, tx_a["id"])["category"]["name"] == "تصنيفي"  # ما تغيّر شي


def test_patch_needs_authentication_and_the_field(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790160012")
    tx = quick_log(client, headers, note="x").json()
    assert client.patch(f"/api/v1/transactions/{tx['id']}", json={"category_id": None}).status_code == 401
    assert client.patch(f"/api/v1/transactions/{tx['id']}", headers=headers, json={}).status_code == 422


# ------------------------------------------------------ مسارات ثانية بتغيّر التصنيف/المصدر

def test_approving_a_category_suggestion_counts_as_a_user_decision(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790160013")
    make_category(db_session, "مطاعم", keywords=["مطعم"])
    entertainment = make_category(db_session, "ترفيه")
    tx = quick_log(client, headers, note="غدا بمطعم").json()
    assert tx["category_origin"] == "auto"
    action = AgentAction(
        user_id=user.id, action_type=AgentActionType.SUGGEST_CATEGORY_CORRECTION, status=AgentActionStatus.PENDING,
        payload={
            "transaction_id": tx["id"], "new_category_id": str(entertainment.id),
            "new_category_name": "ترفيه", "transaction_note": "غدا بمطعم", "transaction_amount": 5.0,
        },
        reasoning="x",
    )
    db_session.add(action)
    db_session.commit()

    assert client.post(f"/api/v1/agent/actions/{action.id}/confirm", headers=headers).status_code == 200

    saved = listed(client, headers, tx["id"])
    assert saved["category"]["name"] == "ترفيه" and saved["category_origin"] == "user"


def test_sms_import_is_labeled_sms_and_uncategorized(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790160014")
    response = client.post("/api/v1/transactions/sms-import/confirm", headers=headers, json={
        "messages": [{"body": BANK_SMS, "received_at": "2026-10-06T14:41:00Z"}],
    })
    item = response.json()[0]
    assert item["source"] == "sms" and item["category"] is None and item["category_origin"] is None


def test_legacy_rows_without_origin_are_returned_safely(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790160015")
    food = make_category(db_session, "مطاعم")
    db_session.add(Transaction(
        user_id=user.id, category_id=food.id, amount=3, type=TransactionType.EXPENSE, source=TransactionSource.MANUAL,
        note="قديمة", occurred_at=datetime.now(timezone.utc),
    ))
    db_session.commit()

    item = client.get("/api/v1/transactions", headers=headers).json()[0]

    assert item["category"]["name"] == "مطاعم"
    assert item["category_origin"] is None and item["ai_suggested"] is False
