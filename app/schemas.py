from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: int
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    """Response shape required by the task: action, task_id, reply."""

    action: str  # create_task | list_tasks | policy_question | rejected | clarification | error
    task_id: int | None = None
    reply: str
class TelegramLinkRequest(BaseModel):
    telegram_user_id: int = Field(gt=0)
    code: str = Field(pattern=r"^[0-9]{6}$")


class TelegramLinkResponse(BaseModel):
    linked: bool
    reply: str


class TelegramResolveRequest(BaseModel):
    telegram_user_id: int = Field(gt=0)


class TelegramResolveResponse(BaseModel):
    employee_id: int
class TelegramIssueCodeRequest(BaseModel):
    employee_id: int = Field(gt=0)


class TelegramIssueCodeResponse(BaseModel):
    employee_id: int
    code: str
    expires_in_seconds: int
    reply: str