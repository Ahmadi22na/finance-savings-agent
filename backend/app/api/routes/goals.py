import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.docs import UNAUTHORIZED, bad_request, not_found, responses
from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalOut, GoalContribution, GoalReorderRequest
from app.services import goal_service

router = APIRouter(prefix="/goals", tags=["Goals"], responses=UNAUTHORIZED)


@router.post(
    "",
    response_model=GoalOut,
    status_code=status.HTTP_201_CREATED,
    summary="إنشاء هدف",
    description=(
        "ينشئ هدفًا جديدًا بأولوية في آخر الترتيب. إذا كان `is_recurring=true` يصبح «مصروفًا "
        "شهريًا ثابتًا»: يُصفَّر تلقائيًا في بداية كل شهر بعد أن يكتمل في الشهر السابق."
    ),
)
def create_goal(
    data: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return goal_service.create_goal(db, current_user, data)


@router.get(
    "",
    response_model=list[GoalOut],
    summary="قائمة الأهداف",
    description=(
        "يرجّع كل أهداف المستخدم مرتبة حسب الحالة ثم الأولوية. يُطبَّق عند القراءة التصفير "
        "الشهري للأهداف المتكررة. `progress_percentage` محسوبة من `current_amount` "
        "و`target_amount`."
    ),
)
def list_goals(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return goal_service.list_goals_for_user(db, current_user)


@router.put(
    "/reorder",
    response_model=list[GoalOut],
    summary="إعادة ترتيب الأولويات",
    description=(
        "يحدّد الترتيب الجديد لكل الأهداف النشطة (من الأعلى أولوية للأقل). يجب إرسال معرّفات "
        "كل الأهداف النشطة الحالية بالضبط، لا أكثر ولا أقل، لتفادي ترتيب جزئي."
    ),
    responses=bad_request("القائمة المرسلة لا تطابق مجموعة الأهداف النشطة الحالية."),
)
def reorder_goals(
    data: GoalReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return goal_service.reorder_goals(db, current_user, data)


@router.post(
    "/{goal_id}/contribute",
    response_model=GoalOut,
    summary="إضافة مبلغ لتقدّم هدف",
    description=(
        "يزيد `current_amount` للهدف بالمبلغ المرسل، ويحوّل حالته إلى `achieved` عند الوصول "
        "للمبلغ المستهدف. للأهداف النشطة فقط."
    ),
    responses=responses(
        bad_request("الهدف غير نشط (منجز أو متروك)."),
        not_found("الهدف غير موجود."),
    ),
)
def contribute_to_goal(
    goal_id: uuid.UUID,
    data: GoalContribution,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return goal_service.contribute_to_goal(db, current_user, goal_id, data)


@router.delete(
    "/{goal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="حذف هدف",
    description=(
        "يحذف الهدف نهائيًا. لا يرجّع محتوى (204)."
    ),
    responses=not_found("الهدف غير موجود."),
)
def delete_goal(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal_service.delete_goal(db, current_user, goal_id)
