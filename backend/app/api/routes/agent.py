import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.docs import UNAUTHORIZED, bad_request, not_found, responses
from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageOut, NudgeOut
from app.schemas.agent_action import AgentActionOut
from app.services import agent_chat_service, nudge_service, agent_action_service

router = APIRouter(prefix="/agent", tags=["Agent"], responses=UNAUTHORIZED)


@router.post(
    "/chat",
    response_model=ChatMessageOut,
    summary="محادثة مع رشيد",
    description=(
        "يرسل رسالة المستخدم لرشيد ويرجّع رده بشخصيته المختارة، مع آخر 20 رسالة كسياق "
        "للمحادثة. قد يولّد رشيد أثناء الرد اقتراحات معلّقة (هدف جديد، تسجيل دخل...) تظهر "
        "لاحقًا في `GET /agent/actions` ولا تُنفَّذ إلا بتأكيد صريح. عند ازدحام خدمة الذكاء "
        "الاصطناعي يرجع الرد 200 مع رسالة اعتذار نصية داخل `reply`."
    ),
    responses=bad_request("المستخدم لم يُكمل الـ Onboarding ولم يختر شخصية لرشيد بعد."),
)
def chat_with_agent(
    data: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reply = agent_chat_service.send_message_to_agent(db, current_user, data.message)
    return ChatMessageOut(reply=reply)


@router.get(
    "/nudge",
    response_model=NudgeOut,
    summary="رسالة مبادِرة من رشيد (Nudge)",
    description=(
        "يستدعيه الموبايل عند فتح التطبيق أو شاشة المحادثة. يرجّع `nudge: null` عندما لا داعي "
        "لرسالة (رد طبيعي وليس خطأ). تُولَّد الرسالة فقط عندما يكون مزاج رشيد «متحمسًا» أو "
        "«قلقًا» (حسب مصاريف المستخدم وتقدّم هدفه)، وبفاصل 12 ساعة على الأقل بين رسالتين."
    ),
)
def get_nudge(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    الموبايل يستدعي هذا الـ Endpoint دوريًا (مثلاً عند فتح التطبيق).
    نرجّع nudge: null لو ولا داعي لأي رسالة هلأ — هذا رد طبيعي متوقع، مش خطأ.
    """
    nudge = nudge_service.check_and_generate_nudge(db, current_user)
    return NudgeOut(nudge=nudge)


@router.get(
    "/actions",
    response_model=list[AgentActionOut],
    summary="الاقتراحات المعلّقة",
    description=(
        "يرجّع اقتراحات رشيد التي لم يرد عليها المستخدم بعد (`pending`)، ويعرضها الموبايل "
        "كبطاقات موافقة/رفض. محتوى `payload` يختلف حسب `action_type`."
    ),
)
def list_pending_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """يرجّع الاقتراحات المعلّقة (PENDING) الحالية — يعرضها الموبايل كبطاقات ينتظر ردّك عليها."""
    return agent_action_service.list_pending_actions(db, current_user)


@router.post(
    "/actions/check",
    response_model=list[AgentActionOut],
    summary="توليد اقتراحات جديدة",
    description=(
        "يفحص وضع المستخدم ويولّد اقتراحات جديدة عند الحاجة: تصحيح تصنيف معاملات غير مصنّفة "
        "(بمساعدة Gemini)، أو دفعة لهدف قريب من الاكتمال. القائمة الفارغة رد طبيعي وليست خطأ. "
        "لا يُنفَّذ أي تعديل هنا؛ الاقتراحات فقط."
    ),
)
def check_for_new_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    يفحص وضع المستخدم ويولّد اقتراحات جديدة لو في داعي فعلي. قائمة فاضية
    رد طبيعي متوقع (مافي شي يستاهل اقتراح هلأ)، مش خطأ.
    """
    return agent_action_service.generate_suggestions(db, current_user)


@router.post(
    "/actions/{action_id}/confirm",
    response_model=AgentActionOut,
    summary="تأكيد اقتراح وتنفيذه",
    description=(
        "ينفّذ الاقتراح فعليًا على بيانات المستخدم بحسب `action_type` (تصحيح تصنيف، دفعة "
        "لهدف، إنشاء هدف، أو تسجيل دخل) ويحوّل حالته إلى `applied`. هذا هو المسار الوحيد الذي "
        "يعدّل فيه رشيد البيانات المالية، ولا يعمل إلا بطلب صريح من المستخدم."
    ),
    responses=responses(
        bad_request("الاقتراح تم الرد عليه سابقًا، أو نوعه غير مدعوم، أو بياناته تالفة."),
        not_found("الاقتراح غير موجود، أو العنصر المرتبط به (معاملة أو هدف) غير موجود."),
    ),
)
def confirm_action(
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ينفّذ الاقتراح فعليًا على بيانات المستخدم. هذا الـ Endpoint الوحيد بكل
    المشروع يلي بيعدّل بيانات مالية بناءً على قرار رشيد — وحتى هو ما بيشتغل
    إلا بطلب صريح من المستخدم (زر "موافق" بالموبايل).
    """
    return agent_action_service.confirm_action(db, current_user, action_id)


@router.post(
    "/actions/{action_id}/reject",
    response_model=AgentActionOut,
    summary="رفض اقتراح",
    description=(
        "يحوّل حالة الاقتراح إلى `rejected` دون أي تعديل على بيانات المستخدم."
    ),
    responses=responses(
        bad_request("الاقتراح تم الرد عليه سابقًا."),
        not_found("الاقتراح غير موجود."),
    ),
)
def reject_action(
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return agent_action_service.reject_action(db, current_user, action_id)
