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
    SmsParseRequest,
    SmsParseResult,
    SmsImportPreviewRequest,
    SmsImportPreviewResponse,
    SmsImportConfirmRequest,
)
from app.services import (
    transaction_service, income_allocation_service, receipt_service, sms_parser_service, sms_import_service,
)
from app.agent.providers.factory import get_ai_provider

router = APIRouter(prefix="/transactions", tags=["Transactions"])

MAX_RECEIPT_IMAGE_BYTES = 10 * 1024 * 1024


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
    """Quick log transaction documentation."""
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

    unallocated = income_allocation_service.unallocated_amounts_for(db, transactions)
    results = []
    for transaction in transactions:
        item = TransactionOut.model_validate(transaction)
        item.unallocated_amount = unallocated.get(transaction.id, 0.0)
        results.append(item)
    return results


@router.post("/scan-receipt", response_model=ReceiptScanResult)
async def scan_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Scan receipt documentation."""
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


@router.post("/parse-sms", response_model=SmsParseResult)
def parse_sms(
    data: SmsParseRequest,
    current_user: User = Depends(get_current_user),
):
    """Parse sms documentation."""
    parsed = sms_parser_service.parse_sms(data.text)
    if parsed is None:
        return SmsParseResult(amount=None, type=None, note=None, parsed=False)

    return SmsParseResult(amount=parsed.amount, type=parsed.type, note=parsed.note, parsed=True)


@router.post("/sms-import/preview", response_model=SmsImportPreviewResponse)
def preview_sms_import(
    data: SmsImportPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview sms import documentation."""
    candidates = sms_import_service.preview_import(db, current_user, data.messages)
    return SmsImportPreviewResponse(candidates=candidates)


@router.post("/sms-import/confirm", response_model=list[TransactionOut], status_code=status.HTTP_201_CREATED)
def confirm_sms_import(
    data: SmsImportConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm sms import documentation."""
    created = sms_import_service.confirm_import(db, current_user, data.messages)
    return [_to_transaction_out(db, t) for t in created]


@router.post("/{transaction_id}/allocate", response_model=IncomeAllocationResult)
def allocate_income(
    transaction_id: uuid.UUID,
    data: IncomeAllocationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Allocate income documentation."""
    transaction, updated_goals = income_allocation_service.allocate_income(
        db, current_user, transaction_id, data
    )
    return IncomeAllocationResult(
        transaction=_to_transaction_out(db, transaction),
        updated_goals=updated_goals,
    )
