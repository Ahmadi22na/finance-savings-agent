from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageOut
from app.services import agent_chat_service

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/chat", response_model=ChatMessageOut)
def chat_with_agent(
    data: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reply = agent_chat_service.send_message_to_agent(db, current_user, data.message)
    return ChatMessageOut(reply=reply)
