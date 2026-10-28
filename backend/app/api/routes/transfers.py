from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.docs import UNAUTHORIZED, bad_request, not_found, responses
from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.transfer import TransferCreate, TransferOut
from app.services import transfer_service

router = APIRouter(prefix="/transfers", tags=["Transfers"], responses=UNAUTHORIZED)


@router.post(
    "",
    response_model=TransferOut,
    status_code=status.HTTP_201_CREATED,
    summary="تحويل بين حسابين للمستخدم",
    description=(
        "ينشئ تحويلاً داخليًا بين حسابين ماليين نشطين للمستخدم بعملية ذرّية واحدة: معاملة خروج (`expense`) من الحساب الأول "
        "ومعاملة دخول (`income`) للثاني، بنفس `transfer_group_id` ونفس المبلغ والوقت والملاحظة. التحويل ليس دخلاً ولا مصروفًا "
        "حقيقيًا: لا يؤثر على مزاج رشيد ولا تقدير المصاريف الأساسية ولا يوزَّع على الأهداف، لكنه يحرّك رصيدي الحسابين. "
        "تعديل أو حذف أي طرف (`PATCH`/`DELETE /transactions/{id}`) يطبَّق على الطرفين."
    ),
    responses=responses(
        bad_request("نفس الحساب، أو أحد الحسابين مؤرشف."),
        not_found("أحد الحسابين غير موجود أو لا يخص المستخدم."),
    ),
)
def create_transfer(
    data: TransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return transfer_service.create_transfer(db, current_user, data)
