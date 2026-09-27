import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.transaction import (
    TransactionQuickLogCreate,
    TransactionOut,
    IncomeAllocationRequest,
    IncomeAllocationResult,
    ReceiptScanResult,
)
from app.services import transaction_service, income_allocation_service, receipt_service
from app.agent.providers.factory import get_ai_provider

router = APIRouter(prefix="/transactions", tags=["Transactions"])

MAX_RECEIPT_IMAGE_BYTES = 10 * 1024 * 1024  # 10 ميغا — كافي جدًا لصورة فاتورة بجودة عادية


def _to_transaction_out(db: Session, transaction) -> TransactionOut:
    result = TransactionOut.model_validate(transaction)
    result.unallocated_amount = income_allocation_service.get_unallocated_amount(db, transaction)
    return result


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
    result = _to_transaction_out(db, transaction)
    result.ai_suggested = ai_suggested
    result.suggestion_confidence = confidence
    return result


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = transaction_service.list_transactions_for_user(db, current_user, limit=limit)
    return [_to_transaction_out(db, t) for t in transactions]


@router.post("/scan-receipt", response_model=ReceiptScanResult)
async def scan_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    يقرأ صورة فاتورة عبر Gemini Vision ويرجّع مسودة (مبلغ + تصنيف مقترح +
    ملاحظة) — ما بيحفظ أي شي. الموبايل يعبّي فيها شاشة التسجيل السريع
    مسبقًا، والمستخدم يراجعها ويحفظها بنفسه عبر /transactions/quick-log
    العادي، بالضبط متل أي تسجيل يدوي.
    """
    if file.content_type not in receipt_service.SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="صيغة الصورة غير مدعومة — استخدم JPEG أو PNG أو WEBP",
        )

    image_bytes = await file.read()
    if len(image_bytes) > MAX_RECEIPT_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حجم الصورة كبير جدًا (الحد الأقصى 10 ميغابايت)",
        )
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="الصورة فاضية")

    provider = get_ai_provider()
    return receipt_service.scan_receipt(db, current_user, provider, image_bytes, file.content_type)


@router.post("/{transaction_id}/allocate", response_model=IncomeAllocationResult)
def allocate_income(
    transaction_id: uuid.UUID,
    data: IncomeAllocationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    توزيع معاملة دخل واحدة على خطة أو أكتر — دايمًا بقرار صريح من المستخدم
    (ما في auto-route تلقائي، هيك قرر أحمد). بتقبل توزيع جزئي (مبلغ أقل من
    كامل الدخل) — الباقي يضل unallocated لحد ما يوزعه المستخدم لاحقًا.
    """
    transaction, updated_goals = income_allocation_service.allocate_income(
        db, current_user, transaction_id, data
    )
    return IncomeAllocationResult(
        transaction=_to_transaction_out(db, transaction),
        updated_goals=updated_goals,
    )
