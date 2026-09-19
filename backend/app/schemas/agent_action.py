import uuid

from pydantic import BaseModel

from app.models.agent import AgentActionType, AgentActionStatus


class AgentActionOut(BaseModel):
    id: uuid.UUID
    action_type: AgentActionType
    status: AgentActionStatus
    payload: dict
    reasoning: str | None

    model_config = {"from_attributes": True}
