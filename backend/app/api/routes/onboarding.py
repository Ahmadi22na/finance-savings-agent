from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.docs import UNAUTHORIZED, bad_request, not_found, responses
from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.onboarding import OnboardingComplete
from app.services import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["Onboarding"], responses=UNAUTHORIZED)


@router.post(
    "/complete",
    response_model=UserOut,
    summary="إتمام الـ Onboarding",
    description=(
        "يعلّم الحساب بأنه أكمل الإعداد، وكل الحقول اختيارية عشان المستخدم يوصل للتطبيق بسرعة: "
        "بدون شخصية بتنختار الشخصية الافتراضية، وبدون نوع دخل بنفترض `variable`، والهدف الأول اختياري "
        "(لو انبعت لازم العنوان والمبلغ مع بعض). طلب فاضي `{}` صالح. يُنفَّذ مرة واحدة فقط لكل حساب."
    ),
    responses=responses(
        bad_request("المستخدم أكمل الـ Onboarding سابقًا، أو ما في أي شخصية متاحة."),
        not_found("الشخصية المختارة غير موجودة."),
    ),
)
def complete_onboarding(
    data: OnboardingComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return onboarding_service.complete_onboarding(db, current_user, data)
