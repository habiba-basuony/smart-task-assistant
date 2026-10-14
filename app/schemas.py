from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: int
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    """Response shape required by the task: action, task_id, reply."""

    action: str  # create_task | list_tasks | policy_question | rejected | clarification | error
    task_id: int | None = None
    reply: str
