from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.docs import UNAUTHORIZED, bad_request, not_found
from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import AccountDeleteRequest, UserOut
from app.schemas.persona import PersonaChange, PersonaFeedbackOut, PersonaFeedbackUpsert
from app.services import account_service, persona_service, usage_service

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
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """أول Endpoint محمي بالتطبيق — أي طلب لازم يوصل توكن صالح بالـ Authorization header."""
    usage_service.record_active_day(db, current_user)  # يوم نشاط واحد باليوم (لقياس العودة للاستخدام)
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


@router.patch(
    "/me/persona",
    response_model=UserOut,
    summary="تبديل شخصية رشيد",
    description=(
        "يبدّل شخصية رشيد في أي وقت (لتجربة الشخصيات الثلاث). يغيّر أسلوب حديث رشيد فقط: الأهداف والمعاملات "
        "وتوزيعات الدخل وحالة رشيد المزاجية تبقى كما هي لأنها مستقلة عن الشخصية. الشخصية لازم تكون مفعّلة."
    ),
    responses=not_found("الشخصية غير موجودة أو غير مفعّلة."),
)
def change_my_persona(
    data: PersonaChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return persona_service.change_persona(db, current_user, data.persona_id)


@router.put(
    "/me/persona-feedback",
    response_model=PersonaFeedbackOut,
    summary="تقييم شخصية رشيد",
    description=(
        "تقييم مختصر (1-5 نجوم + وسوم جاهزة، بدون نص حر) لشخصية من شخصيات رشيد. تقييم واحد لكل شخصية: "
        "إعادة الإرسال تحدّث التقييم السابق. يُستخدم لمعرفة إن كان اختلاف الشخصيات يضيف قيمة فعلية."
    ),
    responses=not_found("الشخصية غير موجودة."),
)
def rate_persona(
    data: PersonaFeedbackUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return persona_service.upsert_feedback(db, current_user, data.persona_id, data.rating, list(data.tags))


@router.get(
    "/me/persona-feedback",
    response_model=list[PersonaFeedbackOut],
    summary="تقييماتي لشخصيات رشيد",
    description="يرجّع تقييمات المستخدم الحالي فقط (الأحدث أولًا)، ليعرض التطبيق التقييم السابق عند إعادة التقييم.",
)
def my_persona_feedback(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return persona_service.list_feedback_for_user(db, current_user)
