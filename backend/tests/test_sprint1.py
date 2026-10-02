"""اختبارات Sprint 1: التصنيفات، التسجيل السريع (Quick-log)، والأهداف."""
import pytest

from app.models.category import Category, CategoryType
from app.services import transaction_service
from app.services.categorizer.rule_based import RuleBasedCategorizer


@pytest.fixture(autouse=True)
def _force_rule_based_categorizer(monkeypatch):
    """
    هاي الاختبارات تحديدًا بتفحص منطق RuleBasedCategorizer (تطابق كلمات
    مفتاحية) بالتحديد — مش "أيًا كان محرك التصنيف المفعّل حاليًا". من بعد
    ما صار factory.get_categorizer() يختار GeminiCategorizer تلقائيًا لو
    GEMINI_API_KEY موجود بالبيئة، صارت هاي الاختبارات (بدون هالفحص) تعتمد
    عن غير قصد على مفتاح AI حقيقي شغال وقت تشغيل pytest — فاشلة لو المفتاح
    غير صالح، وبطيئة/غير حتمية حتى لو اشتغل. منفرض المحرك صراحة.
    """
    monkeypatch.setattr(transaction_service, "get_categorizer", lambda: RuleBasedCategorizer())


@pytest.fixture(autouse=True)
def seed_categories(db_session):
    food = Category(
        name="مطاعم", icon="utensils", is_default=True,
        category_type=CategoryType.EXPENSE, keywords=["مطعم", "قهوة", "أكل"],
    )
    transport = Category(
        name="مواصلات", icon="car", is_default=True,
        category_type=CategoryType.EXPENSE, keywords=["بنزين", "تكسي"],
    )
    db_session.add_all([food, transport])
    db_session.commit()


def get_auth_headers(client, phone="0790001111"):
    response = client.post("/api/v1/auth/register", json={
        "name": "مستخدم اختبار", "phone": phone, "password": "testpassword123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------- Categories ----------

def test_list_categories_returns_defaults(client):
    headers = get_auth_headers(client)
    response = client.get("/api/v1/categories", headers=headers)
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert "مطاعم" in names
    assert "مواصلات" in names


def test_create_custom_category(client):
    headers = get_auth_headers(client)
    response = client.post("/api/v1/categories", headers=headers, json={
        "name": "هوايتي الخاصة", "icon": "star", "category_type": "expense",
    })
    assert response.status_code == 201
    assert response.json()["name"] == "هوايتي الخاصة"
    assert response.json()["is_default"] is False


# ---------- Transactions: مسار الأيقونات (category_id مباشر) ----------

def test_quick_log_with_direct_category(client):
    headers = get_auth_headers(client)
    categories = client.get("/api/v1/categories", headers=headers).json()
    food_id = next(c["id"] for c in categories if c["name"] == "مطاعم")

    response = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 5.5, "type": "expense", "category_id": food_id,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["category"]["name"] == "مطاعم"
    assert data["ai_suggested"] is False


# ---------- Transactions: مسار التصنيف الذكي (note بدون category_id) ----------

def test_quick_log_with_smart_categorization_matches_keyword(client):
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 3.0, "type": "expense", "note": "قهوة مع صاحبي",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["category"]["name"] == "مطاعم"
    assert data["ai_suggested"] is True
    assert data["suggestion_confidence"] > 0


def test_quick_log_with_no_matching_keyword_leaves_uncategorized(client):
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 20.0, "type": "expense", "note": "شي غريب ما إله علاقة",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["category"] is None
    assert data["ai_suggested"] is False


def test_quick_log_requires_category_or_note(client):
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 10.0, "type": "expense",
    })
    assert response.status_code == 422


def test_quick_log_rejects_negative_amount(client):
    headers = get_auth_headers(client)
    response = client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": -5.0, "type": "expense", "note": "قهوة",
    })
    assert response.status_code == 422


def test_list_transactions(client):
    headers = get_auth_headers(client)
    client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": 3.0, "type": "expense", "note": "قهوة",
    })
    response = client.get("/api/v1/transactions", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


# ---------- Goals ----------

def test_create_and_list_goal(client):
    headers = get_auth_headers(client)
    create_response = client.post("/api/v1/goals", headers=headers, json={
        "title": "رحلة سفر", "target_amount": 1000,
    })
    assert create_response.status_code == 201
    assert create_response.json()["progress_percentage"] == 0.0

    list_response = client.get("/api/v1/goals", headers=headers)
    assert len(list_response.json()) == 1


def test_contribute_to_goal_updates_progress(client):
    headers = get_auth_headers(client)
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "مشروع", "target_amount": 500,
    }).json()

    response = client.post(
        f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 250}
    )
    assert response.status_code == 200
    assert response.json()["current_amount"] == 250.0
    assert response.json()["progress_percentage"] == 50.0
    assert response.json()["status"] == "active"


def test_contribute_reaching_target_marks_achieved(client):
    headers = get_auth_headers(client)
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "هدف صغير", "target_amount": 100,
    }).json()

    response = client.post(
        f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 150}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "achieved"


def test_contribute_to_nonexistent_goal_returns_404(client):
    headers = get_auth_headers(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        f"/api/v1/goals/{fake_id}/contribute", headers=headers, json={"amount": 10}
    )
    assert response.status_code == 404
