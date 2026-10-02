from pydantic import BaseModel, Field


class ChatMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ChatMessageOut(BaseModel):
    reply: str


class NudgeOut(BaseModel):
    nudge: str | None
