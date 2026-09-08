from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageOut, NudgeOut
from app.services import agent_chat_service, nudge_service

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/chat", response_model=ChatMessageOut)
def chat_with_agent(
    data: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reply = agent_chat_service.send_message_to_agent(db, current_user, data.message)
    return ChatMessageOut(reply=reply)


@router.get("/nudge", response_model=NudgeOut)
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
