import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.docs import UNAUTHORIZED, bad_request, conflict, not_found, responses
from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.financial_account import (
    AccountCreate,
    AccountOut,
    AccountsSummaryOut,
    AccountUpdate,
    BalanceSnapshotCreate,
    BalanceSnapshotOut,
)
from app.services import financial_account_service

router = APIRouter(prefix="/accounts", tags=["Accounts"], responses=UNAUTHORIZED)

_BALANCE_RULES = (
    "الرصيد = آخر لقطة رصيد + معاملات الحساب التي وقتها بعد وقت اللقطة تمامًا (المعاملة التي وقتها يساوي وقت اللقطة، "
    "أو أقدم منه، لا تُحسب لأن اللقطة تشملها؛ `ignored_before_snapshot` يعدّ المعاملات التي سُجّلت بعد اللقطة بتاريخ "
    "أقدم منها). حساب بدون لقطة رصيده `null` (غير معروف) وليس صفرًا. المعاملات بدون حساب لا تدخل أي رصيد."
)


@router.get(
    "",
    response_model=list[AccountOut],
    summary="قائمة الحسابات المالية",
    description=(
        "يرجّع حسابات المستخدم النشطة (ومعها المؤرشفة إذا `include_archived=true`) مع الرصيد التقديري وجودته. " + _BALANCE_RULES
    ),
)
def list_accounts(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return financial_account_service.list_accounts(db, current_user, include_archived)


@router.post(
    "",
    response_model=AccountOut,
    status_code=status.HTTP_201_CREATED,
    summary="إنشاء حساب مالي",
    description=(
        "ينشئ حسابًا يدويًا (cash أو bank أو wallet) بعملة JOD. `opening_balance` اختياري: يُسجَّل كلقطة مرجعية بوقت الإنشاء، "
        "وبدونه يبقى الرصيد غير معروف. الاسم فريد لكل مستخدم بدون حساسية لحالة الأحرف. الرصيد السالب مسموح."
    ),
    responses=conflict("عندك حساب بنفس الاسم."),
)
def create_account(
    data: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return financial_account_service.create_account(db, current_user, data)


@router.get(
    "/summary",
    response_model=AccountsSummaryOut,
    summary="ملخص الحسابات",
    description=(
        "مجموع أرصدة الحسابات النشطة ذات الرصيد المعروف فقط. إذا `incomplete=true` (في حساب بدون رصيد أو رصيده قديم) "
        "فالمجموع ناقص أو قديم ولا يُعرض كأنه مؤكد."
    ),
)
def accounts_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return financial_account_service.summary(db, current_user)


@router.get(
    "/{account_id}",
    response_model=AccountOut,
    summary="تفاصيل حساب",
    description="يرجّع حسابًا واحدًا مع رصيده وجودته. " + _BALANCE_RULES,
    responses=not_found("الحساب غير موجود."),
)
def get_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return financial_account_service.get_account(db, current_user, account_id)


@router.patch(
    "/{account_id}",
    response_model=AccountOut,
    summary="تعديل حساب",
    description=(
        "تعديل جزئي للاسم أو النوع أو `is_active`. `is_active=false` يؤرشف الحساب: لا يستقبل لقطات جديدة ويبقى سجله "
        "ولقطاته للمراجعة؛ `true` يعيد تفعيله. لازم ترسل حقلاً واحدًا على الأقل ولا يقبل null."
    ),
    responses=responses(not_found("الحساب غير موجود."), conflict("عندك حساب بنفس الاسم.")),
)
def update_account(
    account_id: uuid.UUID,
    data: AccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return financial_account_service.update_account(db, current_user, account_id, data)


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="حذف حساب",
    description=(
        "يحذف الحساب نهائيًا فقط إذا ما عليه أي معاملة ولا لقطة رصيد. غير هيك يرجع 409 والمطلوب أرشفته "
        "(`PATCH` مع `is_active=false`) حفاظًا على السجل التاريخي."
    ),
    responses=responses(not_found("الحساب غير موجود."), conflict("الحساب عليه معاملات أو لقطات رصيد؛ أرشفه بدل الحذف.")),
)
def delete_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    financial_account_service.delete_account(db, current_user, account_id)


@router.post(
    "/{account_id}/balance",
    response_model=AccountOut,
    status_code=status.HTTP_201_CREATED,
    summary="تسجيل رصيد الحساب (لقطة)",
    description=(
        "يضيف لقطة رصيد مرجعية: «رصيد هذا الحساب كان كذا بوقت as_of» (الافتراضي الآن، ولا يقبل المستقبل). اللقطات إضافة فقط "
        "والقديمة تبقى للمراجعة. الحساب المؤرشف لا يقبل لقطات جديدة. " + _BALANCE_RULES
    ),
    responses=responses(
        bad_request("الحساب مؤرشف، أو وقت الرصيد بالمستقبل."),
        not_found("الحساب غير موجود."),
    ),
)
def add_balance_snapshot(
    account_id: uuid.UUID,
    data: BalanceSnapshotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return financial_account_service.add_balance_snapshot(db, current_user, account_id, data)


@router.get(
    "/{account_id}/snapshots",
    response_model=list[BalanceSnapshotOut],
    summary="سجل لقطات رصيد الحساب",
    description="آخر 50 لقطة رصيد للحساب (الأحدث أولاً)، يشمل الحسابات المؤرشفة.",
    responses=not_found("الحساب غير موجود."),
)
def list_snapshots(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return financial_account_service.list_snapshots(db, current_user, account_id)
