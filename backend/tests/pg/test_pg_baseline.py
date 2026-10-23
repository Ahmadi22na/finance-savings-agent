"""
الدفعة 0.A — اختبارات أساس على PostgreSQL (بدون أي تعديل على كود التطبيق).

الغرض: (1) إثبات إننا فعلاً على PostgreSQL، (2) توثيق مشكلة الدقة الحالية بدليل،
(3) إثبات أشياء SQLite ما بتكشفها (FK حقيقي، قيد UNIQUE).

اختبارا الدقة كانا xfail(strict) قبل الدفعة 0.B؛ بعد توسيع الأعمدة لـ NUMERIC(14,3)
صاروا اختبارات عادية لازم تنجح.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.models.transaction import Transaction, TransactionSource, TransactionType
from app.models.user import User


def _make_user(db, phone="0790000001"):
    user = User(name="pg test", phone=phone, hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _tx(user, amount, **extra):
    return Transaction(
        user_id=user.id,
        amount=amount,
        type=TransactionType.EXPENSE,
        source=TransactionSource.MANUAL,
        occurred_at=datetime.now(timezone.utc),
        **extra,
    )


def test_engine_is_really_postgres(db_session):
    assert db_session.bind.dialect.name == "postgresql"


def test_foreign_key_is_enforced(db_session):
    """SQLite بدون PRAGMA ما بيفرض FK — PostgreSQL بيفرضه."""
    db_session.add(_tx(type("U", (), {"id": uuid.uuid4()})(), Decimal("1.000")))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_external_ref_unique_per_user(db_session):
    user = _make_user(db_session)
    db_session.add(_tx(user, Decimal("1.00"), external_ref="a" * 64))
    db_session.commit()
    db_session.add(_tx(user, Decimal("2.00"), external_ref="a" * 64))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_three_decimal_amount_is_preserved(db_session):
    user = _make_user(db_session)
    tx = _tx(user, Decimal("4.505"))
    db_session.add(tx)
    db_session.commit()
    db_session.expire_all()
    stored = db_session.query(Transaction.amount).filter(Transaction.id == tx.id).scalar()
    assert Decimal(stored) == Decimal("4.505")


def test_sum_of_500_three_decimal_amounts_has_no_drift(db_session):
    user = _make_user(db_session)
    amounts = [Decimal("1.000") + Decimal(i % 7) / Decimal(1000) for i in range(500)]
    db_session.add_all([_tx(user, amount) for amount in amounts])
    db_session.commit()
    stored_total = db_session.query(func.sum(Transaction.amount)).scalar()
    assert Decimal(stored_total) == sum(amounts)
