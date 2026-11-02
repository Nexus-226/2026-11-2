from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent.chat import ToolCallSummary


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    pet_id: UUID | None = None
    session_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 4000:
            raise ValueError("message must contain 1 to 4000 characters")
        return value


class ChatResponse(BaseModel):
    session_id: UUID
    message_id: UUID
    reply: str
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)
