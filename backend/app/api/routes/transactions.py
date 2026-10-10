import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.docs import UNAUTHORIZED, bad_request, conflict, not_found, responses
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

router = APIRouter(prefix="/transactions", tags=["Transactions"], responses=UNAUTHORIZED)

MAX_RECEIPT_IMAGE_BYTES = 10 * 1024 * 1024  # 10 ميغا — كافي جدًا لصورة فاتورة بجودة عادية


def _to_transaction_out(db: Session, transaction) -> TransactionOut:
    result = TransactionOut.model_validate(transaction)
    result.unallocated_amount = income_allocation_service.get_unallocated_amount(db, transaction)
    return result


@router.post(
    "/quick-log",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
    summary="تسجيل سريع لمعاملة",
    description=(
        "المسار الأهم بالتطبيق، ويدعم مسارين: (1) الأيقونات: إرسال `category_id` يحفظ فورًا "
        "بدون أي معالجة ذكية. (2) النص الذكي: إرسال `note` بدون `category_id` يجعل محرك "
        "التصنيف يخمّن التصنيف تلقائيًا، ويرجع `ai_suggested=true` مع "
        "`suggestion_confidence`. يجب إرسال `category_id` أو `note` على الأقل."
    ),
)
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


@router.get(
    "",
    response_model=list[TransactionOut],
    summary="قائمة المعاملات",
    description=(
        "يرجّع آخر معاملات المستخدم (الأحدث أولًا). لمعاملات الدخل، `unallocated_amount` هو "
        "المبلغ الذي لم يُوزَّع بعد على أهداف."
    ),
)
def list_transactions(
    limit: int = Query(50, description="عدد المعاملات المطلوب إرجاعها (الافتراضي 50)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = transaction_service.list_transactions_for_user(db, current_user, limit=limit)
    # طلب SQL واحد لكل unallocated بدل طلب لكل معاملة (N+1)
    unallocated = income_allocation_service.unallocated_amounts_for(db, transactions)
    results = []
    for transaction in transactions:
        item = TransactionOut.model_validate(transaction)
        item.unallocated_amount = unallocated.get(transaction.id, 0.0)
        results.append(item)
    return results


@router.post(
    "/scan-receipt",
    response_model=ReceiptScanResult,
    summary="قراءة فاتورة من صورة (OCR)",
    description=(
        "يستقبل صورة فاتورة (multipart، الحقل `file`، بصيغة JPEG أو PNG أو WEBP وبحد أقصى 10 "
        "ميغابايت) فيقرأها Gemini Vision ويرجّع **مسودة** فقط: مبلغ وتصنيف مقترح وملاحظة. لا "
        "يحفظ أي شيء؛ يراجع المستخدم المسودة ثم يحفظها عبر `POST /transactions/quick-log`. "
        "القيمة `readable=false` تعني أن الصورة غير واضحة أو ليست فاتورة."
    ),
    responses=bad_request("صيغة الصورة غير مدعومة، أو حجمها أكبر من 10 ميغابايت، أو الصورة فارغة."),
)
async def scan_receipt(
    file: UploadFile = File(..., description="صورة الفاتورة (JPEG أو PNG أو WEBP، حتى 10 ميغابايت)"),
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


@router.post(
    "/parse-sms",
    response_model=SmsParseResult,
    summary="تحليل رسالة بنكية ملصوقة",
    description=(
        "يحلّل نص رسالة بنكية (نسخ ولصق يدوي، بدون أي صلاحية قراءة رسائل) ويرجّع **مسودة** "
        "(مبلغ، نوع، ملاحظة). لا يحفظ شيئًا. القيمة `parsed=false` تعني أن النص لا يطابق أي "
        "نمط مدعوم."
    ),
)
def parse_sms(
    data: SmsParseRequest,
    current_user: User = Depends(get_current_user),
):
    """
    يحلل نص رسالة بنكية ملصوقة يدويًا (Copy-Paste، بدون أي صلاحية قراءة
    رسائل) ويرجّع مسودة — نفس فلسفة /scan-receipt بالضبط، ما بيحفظ أي شي.
    """
    parsed = sms_parser_service.parse_sms(data.text)
    if parsed is None:
        return SmsParseResult(amount=None, type=None, note=None, parsed=False)

    return SmsParseResult(amount=parsed.amount, type=parsed.type, note=parsed.note, parsed=True)


@router.post(
    "/sms-import/preview",
    response_model=SmsImportPreviewResponse,
    summary="معاينة استيراد رسائل بنكية",
    description=(
        "يحلّل رسائل قُرئت من صندوق الوارد على الجهاز (بعد فلترة محلية، حتى 300 رسالة) ويرجّع "
        "المعاملات المكتشفة مع علامة `already_imported` للرسائل المستوردة سابقًا. لا يحفظ "
        "شيئًا."
    ),
)
def preview_sms_import(
    data: SmsImportPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    يحلل رسائل مقروءة من صندوق الوارد (بعد فلترة محلية على الموبايل) ويرجّع
    المعاملات المكتشفة مع علامة already_imported — ما بيحفظ أي شي.
    """
    candidates = sms_import_service.preview_import(db, current_user, data.messages)
    return SmsImportPreviewResponse(candidates=candidates)


@router.post(
    "/sms-import/confirm",
    response_model=list[TransactionOut],
    status_code=status.HTTP_201_CREATED,
    summary="تأكيد استيراد الرسائل",
    description=(
        "ينشئ معاملات فعلية من الرسائل التي اختارها المستخدم. السيرفر يعيد تحليل نص كل رسالة "
        "بنفسه ولا يثق بأي مبلغ قادم من الموبايل، ويتجاهل الرسائل المستوردة مسبقًا."
    ),
    responses=conflict("بعض الرسائل استُوردت للتو بطلب آخر؛ حدّث القائمة وأعد المحاولة."),
)
def confirm_sms_import(
    data: SmsImportConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ينشئ معاملات فعلية من الرسائل يلي اختارها المستخدم. السيرفر بيعيد تحليل
    نص كل رسالة بنفسه (ما بيثق بأي رقم من الموبايل)، وبيتجاهل يلي انستوردت
    قبل.
    """
    created = sms_import_service.confirm_import(db, current_user, data.messages)
    return [_to_transaction_out(db, t) for t in created]


@router.post(
    "/{transaction_id}/allocate",
    response_model=IncomeAllocationResult,
    summary="توزيع دخل على الأهداف",
    description=(
        "يوزّع معاملة دخل واحدة على هدف أو أكثر بقرار صريح من المستخدم (لا يوجد توجيه "
        "تلقائي). يقبل توزيعًا جزئيًا؛ يبقى الباقي في `unallocated_amount` حتى يوزّعه "
        "المستخدم لاحقًا. يرجّع المعاملة بعد التحديث والأهداف التي تغيّرت."
    ),
    responses=responses(
        bad_request("المعاملة ليست دخلًا، أو هدف مكرر/غير موجود/غير نشط، أو المبلغ أكبر من المتاح."),
        not_found("المعاملة غير موجودة."),
    ),
)
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
