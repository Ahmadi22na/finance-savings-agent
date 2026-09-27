"""اختبارات قراءة الفواتير عبر Gemini Vision (Sprint 8 — OCR)."""
import io

import pytest

from app.agent.providers.base import AgentReply
from app.api.routes import transactions as transactions_route
from app.models.category import Category, CategoryType


class FakeImageProvider:
    """يحاكي BaseAIProvider.analyze_image بدون أي استدعاء حقيقي لـ Gemini."""
    def __init__(self, text):
        self.text = text
        self.calls = []

    def analyze_image(self, system_prompt, user_message, image_bytes, mime_type):
        self.calls.append((system_prompt, user_message, image_bytes, mime_type))
        return AgentReply(text=self.text)

    def generate_reply(self, *args, **kwargs):
        raise NotImplementedError("مش مستخدمة بهاي الاختبارات")


def patch_image_provider(monkeypatch, fake):
    # الـ route استورد get_ai_provider مباشرة بالاسم (from ... import get_ai_provider)،
    # فلازم نصحّح النسخة المستوردة جوا الموديول نفسه، مش بس مكان تعريفها الأصلي
    monkeypatch.setattr(transactions_route, "get_ai_provider", lambda: fake)


@pytest.fixture(autouse=True)
def seed_categories(db_session):
    food = Category(
        name="مطاعم", icon="utensils", is_default=True,
        category_type=CategoryType.EXPENSE, keywords=["مطعم"],
    )
    db_session.add(food)
    db_session.commit()
    return {"food": str(food.id)}


def get_auth_headers(client, phone="0790020001"):
    response = client.post("/api/v1/auth/register", json={
        "name": "مستخدم اختبار", "phone": phone, "password": "testpassword123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def fake_image_file():
    # محتوى الصورة نفسه مش مهم للاختبار — الفحص كله على منطق التحقق
    # والتنظيف حوالين رد الـ AI، مش على قراءة بايتات صورة حقيقية
    return ("receipt.jpg", io.BytesIO(b"fake-jpeg-bytes"), "image/jpeg")


def test_scan_receipt_returns_amount_and_category(client, db_session, monkeypatch, seed_categories):
    headers = get_auth_headers(client)
    fake = FakeImageProvider(
        f'{{"amount": 12.5, "category_id": "{seed_categories["food"]}", "note": "مطعم الحارة"}}'
    )
    patch_image_provider(monkeypatch, fake)

    response = client.post(
        "/api/v1/transactions/scan-receipt", headers=headers,
        files={"file": fake_image_file()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["amount"] == 12.5
    assert body["category_id"] == seed_categories["food"]
    assert body["category_name"] == "مطاعم"
    assert body["note"] == "مطعم الحارة"
    assert body["readable"] is True

    # نتأكد إنه فعليًا الصورة والـ mime_type وصلوا للـ provider صح
    assert fake.calls[0][3] == "image/jpeg"


def test_scan_receipt_handles_unreadable_image(client, db_session, monkeypatch, seed_categories):
    """صورة غير واضحة أو مش فاتورة أصلًا — رشيد يرجّع null بدل ما يخترع أرقام."""
    headers = get_auth_headers(client)
    fake = FakeImageProvider('{"amount": null, "category_id": null, "note": null}')
    patch_image_provider(monkeypatch, fake)

    response = client.post(
        "/api/v1/transactions/scan-receipt", headers=headers,
        files={"file": fake_image_file()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["amount"] is None
    assert body["readable"] is False


def test_scan_receipt_ignores_unknown_category_id(client, db_session, monkeypatch, seed_categories):
    """لو الموديل اخترع category_id مش موجود فعليًا، نتجاهله بدل ما نخزّن بيانات فاسدة."""
    headers = get_auth_headers(client)
    fake = FakeImageProvider('{"amount": 20, "category_id": "not-a-real-id", "note": "شي ما"}')
    patch_image_provider(monkeypatch, fake)

    response = client.post(
        "/api/v1/transactions/scan-receipt", headers=headers,
        files={"file": fake_image_file()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["amount"] == 20.0
    assert body["category_id"] is None
    assert body["readable"] is True  # المبلغ نفسه انقرأ صح، بس التصنيف تجاهلناه


def test_scan_receipt_rejects_malformed_json_gracefully(client, db_session, monkeypatch, seed_categories):
    headers = get_auth_headers(client)
    fake = FakeImageProvider("هاد مش JSON أصلًا")
    patch_image_provider(monkeypatch, fake)

    response = client.post(
        "/api/v1/transactions/scan-receipt", headers=headers,
        files={"file": fake_image_file()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["readable"] is False


def test_scan_receipt_rejects_unsupported_file_type(client, db_session):
    headers = get_auth_headers(client)
    response = client.post(
        "/api/v1/transactions/scan-receipt", headers=headers,
        files={"file": ("receipt.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert response.status_code == 400


def test_scan_receipt_never_creates_a_transaction(client, db_session, monkeypatch, seed_categories):
    """أهم قرار تصميم بهالميزة: القراءة لحالها ما لازم تنشئ أي معاملة حقيقية."""
    headers = get_auth_headers(client)
    fake = FakeImageProvider(
        f'{{"amount": 12.5, "category_id": "{seed_categories["food"]}", "note": "مطعم"}}'
    )
    patch_image_provider(monkeypatch, fake)

    client.post(
        "/api/v1/transactions/scan-receipt", headers=headers,
        files={"file": fake_image_file()},
    )

    transactions = client.get("/api/v1/transactions", headers=headers).json()
    assert transactions == []
