"""
اختبارات أساسية لتدفق التسجيل والدخول.
تستخدم SQLite في الذاكرة بدل PostgreSQL عشان تشتغل بسرعة بدون Docker —
هذا شائع بالاختبارات الوحدوية (Unit Tests)، بينما الـ Integration Tests الحقيقية
لازم تشتغل ضد PostgreSQL فعلي (نضيفها لاحقًا بـ CI).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.session import Base, get_db
from app import models  # noqa: F401  — يسجّل كل الجداول بـ Base.metadata قبل create_all

# StaticPool ضروري هون: بدونه SQLite in-memory بينشئ قاعدة بيانات جديدة فارغة
# مع كل اتصال جديد، فبتضيع الجداول المُنشأة. StaticPool بيضمن استخدام نفس الاتصال دايمًا.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def test_register_creates_user_and_returns_tokens():
    response = client.post("/api/v1/auth/register", json={
        "name": "أحمد",
        "phone": "0790000000",
        "password": "strongpassword123",
        "income_type": "variable",
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["name"] == "أحمد"
    assert data["user"]["agent_name"] == "رشيد"


def test_register_duplicate_phone_fails():
    payload = {"name": "أحمد", "phone": "0790000001", "password": "strongpassword123"}
    client.post("/api/v1/auth/register", json=payload)
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


def test_login_with_correct_credentials():
    client.post("/api/v1/auth/register", json={
        "name": "سارة", "phone": "0790000002", "password": "mypassword123",
    })
    response = client.post("/api/v1/auth/login", json={
        "phone": "0790000002", "password": "mypassword123",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_wrong_password_fails():
    client.post("/api/v1/auth/register", json={
        "name": "سارة", "phone": "0790000003", "password": "mypassword123",
    })
    response = client.post("/api/v1/auth/login", json={
        "phone": "0790000003", "password": "wrongpassword",
    })
    assert response.status_code == 401


def test_protected_route_requires_token():
    response = client.get("/api/v1/users/me")
    assert response.status_code in (401, 403)


def test_protected_route_with_valid_token():
    register_response = client.post("/api/v1/auth/register", json={
        "name": "ليلى", "phone": "0790000004", "password": "mypassword123",
    })
    token = register_response.json()["access_token"]
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["phone"] == "0790000004"
