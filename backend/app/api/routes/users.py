from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.docs import UNAUTHORIZED, bad_request
from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import AccountDeleteRequest, UserOut
from app.services import account_service

router = APIRouter(prefix="/users", tags=["Users"], responses=UNAUTHORIZED)


@router.get(
    "/me",
    response_model=UserOut,
    summary="بيانات المستخدم الحالي",
    description=(
        "يرجّع ملف المستخدم صاحب التوكن، بما فيه الشخصية المختارة وحالة إتمام الـ Onboarding. "
        "يستخدمه التطبيق عند الإقلاع للتحقق من صلاحية التوكن وتوجيه المستخدم للشاشة المناسبة."
    ),
)
def get_me(current_user: User = Depends(get_current_user)):
    """أول Endpoint محمي بالتطبيق — أي طلب لازم يوصل توكن صالح بالـ Authorization header."""
    return current_user


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="حذف الحساب وكل بياناتي",
    description=(
        "يحذف حساب المستخدم نهائيًا مع كل بياناته: الأهداف والمعاملات وتوزيعات الدخل ومحادثات رشيد "
        "والاقتراحات وسجل استهلاك الذكاء الاصطناعي والتصنيفات الخاصة. لا يمكن التراجع. "
        "يتطلب كلمة المرور وتأكيدًا صريحًا (`confirm: true`)، ويصبح التوكن غير صالح فورًا ويمكن "
        "استخدام نفس رقم الهاتف لحساب جديد. لا يرجّع محتوى (204)."
    ),
    responses=bad_request("كلمة المرور غير صحيحة."),
)
def delete_me(
    data: AccountDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_service.delete_account(db, current_user, data.password)
