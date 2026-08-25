from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.transaction import TransactionQuickLogCreate, TransactionOut
from app.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/quick-log", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def quick_log_transaction(
    data: TransactionQuickLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    التسجيل السريع — المسار الأهم بالتطبيق كامل.
    - وصل category_id؟ → حفظ فوري بدون أي معالجة إضافية (مسار الأيقونات)
    - ما وصل category_id بس وصل note؟ → محرك التصنيف الذكي يحاول يخمّن (مسار النص)
    """
    transaction, ai_suggested, confidence = transaction_service.create_quick_log_transaction(
        db, current_user, data
    )
    result = TransactionOut.model_validate(transaction)
    result.ai_suggested = ai_suggested
    result.suggestion_confidence = confidence
    return result


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return transaction_service.list_transactions_for_user(db, current_user, limit=limit)
