"""
إعداد مشترك لكل الاختبارات.
المشكلة يلي هذا الملف بيحلها: كل ملف اختبار كان عنده محرك SQLite خاص فيه،
وبما إنهم كلهم بيعدّلوا نفس app.dependency_overrides (لأن app واحد مشترك بين كل الملفات)،
آخر ملف يتحمّل كان يفوز، وبيخلي بقية الملفات تشتغل ضد قاعدة بيانات فارغة (بدون جداول).
الحل: محرك واحد مشترك هون، وكل الملفات تستورده بدل ما تعمل نسخته الخاصة فيها.
"""
import os

# لازم ينضبط قبل أي استيراد من app.* — JWT_SECRET_KEY صار إلزامي بدون قيمة
# افتراضية بالكود (نفس إصلاح config.py)، فبدون هالسطر pytest كانت رح تفشل
# بالكامل من أول استيراد. setdefault يحترم أي قيمة حقيقية موجودة أصلًا
# بالبيئة (مثلاً CI عندها سر خاص)، وبس يعبّي قيمة وهمية لو ما في شي مضبوط.
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-never-used-in-production")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.session import Base, get_db
from app import models  # noqa: F401

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def clean_tables():
    """يصفّر كل الجداول قبل كل اختبار — عزل كامل بين الاختبارات بدون تكرار كود."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    yield session
    session.close()
