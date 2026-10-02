"""Module documentation."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionType
from app.models.user import User


MIN_HISTORY_DAYS_FOR_ESTIMATE = 14


@dataclass
class EssentialsEstimate:
    monthly_amount: float | None
    source: str  # "profile" | "history" | "unavailable"
    note: str


def get_essentials_estimate(db: Session, user: User) -> EssentialsEstimate:

    if user.estimated_monthly_essentials is not None:
        return EssentialsEstimate(
            monthly_amount=float(user.estimated_monthly_essentials),
            source="profile",
            note=(
                f"عندك تقدير محفوظ مسبقًا لمصاريف المستخدم الأساسية الشهرية: "
                f"{float(user.estimated_monthly_essentials):.0f} دينار تقريبًا."
            ),
        )


    cutoff = datetime.now(timezone.utc) - timedelta(days=MIN_HISTORY_DAYS_FOR_ESTIMATE)
    oldest_transaction = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id, Transaction.occurred_at < cutoff)
        .first()
    )
    if oldest_transaction is not None:
        expenses = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == user.id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.occurred_at >= cutoff,
            )
            .all()
        )
        total = sum(float(t.amount) for t in expenses)
        days_covered = MIN_HISTORY_DAYS_FOR_ESTIMATE
        monthly_estimate = round((total / days_covered) * 30, 2)
        return EssentialsEstimate(
            monthly_amount=monthly_estimate,
            source="history",
            note=(
                f"ما عندك رقم محفوظ، بس حسب تاريخ مصاريفه الفعلي آخر أسبوعين، "
                f"تقدير مصاريفه الأساسية الشهرية تقريبًا {monthly_estimate:.0f} دينار "
                f"(هذا تقدير تقريبي بس، وضحه للمستخدم إذا استخدمته)."
            ),
        )


    return EssentialsEstimate(
        monthly_amount=None,
        source="unavailable",
        note=(
            "ما في عندك أي تقدير لمصاريف المستخدم الأساسية (لا محفوظ ولا من تاريخ كافي). "
            "إذا احتجت هالرقم لبناء اقتراح هدف، اسأل المستخدم مباشرة بسؤال بسيط "
            "(مثلاً: كم بتتوقع تصرف أسبوعيًا أو شهريًا على الأكل والمواصلات؟)."
        ),
    )
