from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionSource
from app.models.user import User
from app.schemas.transaction import TransactionQuickLogCreate
from app.services import category_service
from app.services.categorizer.factory import get_categorizer



AUTO_APPLY_CONFIDENCE_THRESHOLD = 0.6


def create_quick_log_transaction(
    db: Session, user: User, data: TransactionQuickLogCreate
) -> tuple[Transaction, bool, float | None]:
    """Create quick log transaction documentation."""
    ai_suggested = False
    suggestion_confidence: float | None = None
    category_id = data.category_id

    if category_id is None:

        available_categories = category_service.list_categories_for_user(db, user)
        categorizer = get_categorizer()
        suggestion = categorizer.suggest_category(data.note or "", available_categories)

        if suggestion.category_id is not None:
            category_id = suggestion.category_id
            ai_suggested = True
            suggestion_confidence = suggestion.confidence



    transaction = Transaction(
        user_id=user.id,
        category_id=category_id,
        amount=data.amount,
        type=data.type,
        source=TransactionSource.MANUAL,
        note=data.note,
        occurred_at=data.occurred_at or datetime.now(timezone.utc),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return transaction, ai_suggested, suggestion_confidence


def list_transactions_for_user(db: Session, user: User, limit: int = 50) -> list[Transaction]:
    return (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id)
        .order_by(Transaction.occurred_at.desc())
        .limit(limit)
        .all()
    )


def get_transaction_or_404(db: Session, user: User, transaction_id) -> Transaction:
    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == user.id)
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المعاملة غير موجودة")
    return transaction
