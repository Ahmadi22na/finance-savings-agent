"""
اختبارات سكربت بيانات الـ Demo (app/scripts/seed_demo.py).
بنتأكد إنه: بيطلّع المزاج المطلوب فعلاً حسب الـ Mood Engine، توزيع الدخل
متطابق مع تقدم كل هدف، وإعادة التشغيل ما بتكرر الحساب. وإنه الـ API
بيقدر يسجّل دخول بالحساب التجريبي ويقرأ بياناته.
"""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func

from app.models.category import Category, CategoryType
from app.models.goal import Goal
from app.models.income_allocation import IncomeAllocation
from app.models.persona import Persona
from app.models.transaction import Transaction
from app.models.user import User
from app.scripts.seed_demo import build_demo

PHONE = "0799000000"
PASSWORD = "demo1234"


def _seed_reference_data(db):
    """التصنيفات والشخصيات بتجي من الـ Migrations بالإنتاج — هون منعيدها للاختبار."""
    migration = next(Path(__file__).parent.parent.glob("alembic/versions/*seed_default_categories.py"))
    spec = importlib.util.spec_from_file_location("seed_categories_migration", migration)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for c in module.DEFAULT_CATEGORIES:
        db.add(Category(
            name=c["name"], icon=c["icon"], is_default=True,
            category_type=CategoryType[c["type"]], keywords=c["keywords"],
        ))
    for key in ("wise", "business", "energetic"):
        db.add(Persona(
            key=key, display_name=key, tagline="t", color_hex="#000000",
            system_prompt="p", is_active=True,
        ))
    db.commit()


@pytest.mark.parametrize("mood", ["energized", "concerned", "neutral"])
def test_seed_produces_requested_mood(db_session, mood):
    _seed_reference_data(db_session)
    result = build_demo(db_session, "energetic", mood, PHONE, PASSWORD)
    assert result["mood"].state.value == mood


def test_allocations_match_goal_progress(db_session):
    _seed_reference_data(db_session)
    build_demo(db_session, "wise", "energized", PHONE, PASSWORD)
    for goal in db_session.query(Goal).all():
        allocated = db_session.query(
            func.coalesce(func.sum(IncomeAllocation.amount), 0)
        ).filter(IncomeAllocation.goal_id == goal.id).scalar()
        assert float(allocated) == pytest.approx(float(goal.current_amount))


def test_seed_is_idempotent(db_session):
    _seed_reference_data(db_session)
    build_demo(db_session, "energetic", "neutral", PHONE, PASSWORD)
    first_count = db_session.query(Transaction).count()
    build_demo(db_session, "energetic", "neutral", PHONE, PASSWORD)
    assert db_session.query(User).filter(User.phone == PHONE).count() == 1
    assert db_session.query(Transaction).count() == first_count  # نفس البيانات الثابتة، بدون تكرار


def test_demo_account_works_through_api(client, db_session):
    _seed_reference_data(db_session)
    build_demo(db_session, "energetic", "energized", PHONE, PASSWORD)

    login = client.post("/api/v1/auth/login", json={"phone": PHONE, "password": PASSWORD})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    goals = client.get("/api/v1/goals", headers=headers)
    assert goals.status_code == 200
    assert len(goals.json()) == 4

    transactions = client.get("/api/v1/transactions?limit=500", headers=headers)
    assert transactions.status_code == 200
    assert len(transactions.json()) > 100

    pending = client.get("/api/v1/agent/actions", headers=headers)
    assert pending.status_code == 200
    assert len(pending.json()) == 2
