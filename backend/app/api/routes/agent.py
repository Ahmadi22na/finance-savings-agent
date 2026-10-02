import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageOut, NudgeOut
from app.schemas.agent_action import AgentActionOut
from app.services import agent_chat_service, nudge_service, agent_action_service

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
    """Get nudge documentation."""
    nudge = nudge_service.check_and_generate_nudge(db, current_user)
    return NudgeOut(nudge=nudge)


@router.get("/actions", response_model=list[AgentActionOut])
def list_pending_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List pending actions documentation."""
    return agent_action_service.list_pending_actions(db, current_user)


@router.post("/actions/check", response_model=list[AgentActionOut])
def check_for_new_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check for new actions documentation."""
    return agent_action_service.generate_suggestions(db, current_user)


@router.post("/actions/{action_id}/confirm", response_model=AgentActionOut)
def confirm_action(
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm action documentation."""
    return agent_action_service.confirm_action(db, current_user, action_id)


@router.post("/actions/{action_id}/reject", response_model=AgentActionOut)
def reject_action(
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return agent_action_service.reject_action(db, current_user, action_id)
