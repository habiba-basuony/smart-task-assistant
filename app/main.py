import json
import logging
import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, Employee, Task
from app.schemas import ChatRequest, ChatResponse
from app.seed import initialize_database
from app.services.authorization_service import AuthorizationError, tasks_for_scope
from app.services.date_service import WEEKDAYS_AR
from app.services.llm_service import LLMNotConfiguredError, parse_intent
from app.services.rag_service import RAGNotConfiguredError, answer_policy_question
from app.services.task_service import NeedsClarification, create_task, find_employee
from app.services.text_utils import normalize_ar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smart_task_assistant")

# Exact phrases for "my tasks". They are answered without the LLM (cheap, and always the same).
MY_TASKS_PHRASES = {"وش مهامي", "ايش مهامي", "ما هي مهامي", "مهامي", "اعرض مهامي", "عرض مهامي", "وريني مهامي"}
# Safety net: if the LLM misses a request for everybody's tasks, the code still checks the role.
ALL_TASKS_HINTS = ("كل مهام", "جميع مهام", "مهام الشركه", "مهام الجميع")
STATUS_AR = {"pending": "قيد التنفيذ", "done": "مكتملة"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Smart Task Assistant", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- helpers ----------

def respond(actor: Employee, action: str, reply: str, task_id: int | None = None) -> ChatResponse:
    logger.info("audit user=%s role=%s action=%s task_id=%s", actor.id, actor.role, action, task_id)
    return ChatResponse(action=action, task_id=task_id, reply=reply)
def save_audit(
    db: Session,
    user_id: int | None,
    user_role: str | None,
    action: str,
    task_id: int | None = None,
) -> None:
    """Persist an audit event without storing the user's message."""
    try:
        entry = AuditLog(
            user_id=user_id,
            user_role=user_role,
            action=action[:50],
            task_id=task_id,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist audit event")


def audit_response(
    db: Session,
    actor: Employee,
    response: ChatResponse | JSONResponse,
):
    """Record the response action, then return the original response unchanged."""
    if isinstance(response, JSONResponse):
        try:
            data = json.loads(response.body)
        except (ValueError, TypeError):
            data = {}

        action = data.get("action", "error")
        task_id = data.get("task_id")
    else:
        action = response.action
        task_id = response.task_id

    if not isinstance(task_id, int):
        task_id = None

    save_audit(
        db=db,
        user_id=actor.id,
        user_role=str(actor.role),
        action=str(action),
        task_id=task_id,
    )

    return response

def error_response(status_code: int, reply: str) -> JSONResponse:
    # Same JSON shape as a normal answer. Technical details go to the log, never to the user.
    return JSONResponse(status_code=status_code, content={"action": "error", "task_id": None, "reply": reply})


def format_due(due_date, due_time) -> str:
    if due_date is None:
        return "بدون موعد محدد"
    text = f"{WEEKDAYS_AR[due_date.weekday()]} {due_date.isoformat()}"
    if due_time:
        text += f" الساعة {due_time.strftime('%H:%M')}"
    return text


def format_tasks(tasks: list[Task]) -> str:
    return "\n".join(
        f"- #{t.id}: {t.description} | المسؤول: {t.assignee.name} | "
        f"الموعد: {format_due(t.due_date, t.due_time)} | الحالة: {STATUS_AR.get(t.status, t.status)}"
        for t in tasks
    )


def not_found_reply(actor: Employee, name: str) -> ChatResponse:
    return respond(actor, "clarification", f"لم أجد موظفًا باسم «{name}». يُرجى كتابة الاسم كما هو مسجّل.")


# ---------- one handler per intent ----------

def handle_list(db: Session, actor: Employee, scope: str, name: str | None) -> ChatResponse:
    target = None
    if scope == "person":
        if not name:
            return respond(actor, "clarification", "ما اسم الموظف المطلوب عرض مهامه؟")
        target = find_employee(db, name)
        if target is None:
            return not_found_reply(actor, name)
    try:
        tasks = tasks_for_scope(db, actor, scope, target).order_by(Task.id.asc()).all()
    except AuthorizationError as exc:
        return respond(actor, "rejected", str(exc))
    if not tasks:
        return respond(actor, "list_tasks", "لا توجد مهام لعرضها.")
    return respond(actor, "list_tasks", "المهام المتاحة لك:\n" + format_tasks(tasks))


def handle_create(
    db: Session, actor: Employee, assignee_name: str | None, description: str | None, message: str
) -> ChatResponse:
    assignee = find_employee(db, assignee_name) if assignee_name else actor
    if assignee is None:
        return not_found_reply(actor, assignee_name)
    try:
        task, due = create_task(db, actor, assignee, description, message)
    except AuthorizationError as exc:
        return respond(actor, "rejected", str(exc))
    except NeedsClarification as exc:
        return respond(actor, "clarification", str(exc))

    if assignee.id == actor.id:
        reply = f"تم تسجيل المهمة «{task.description}» لك."
    else:
        reply = f"تم تسجيل المهمة «{task.description}» وإسنادها إلى {assignee.name}."
    reply += f" الموعد: {format_due(due.due_date, due.due_time)}." if due.due_date else " بدون موعد محدد."
    if due.moved_from_friday:
        reply += " ملاحظة: الجمعة إجازة ولا تُسجَّل فيها مهام، لذلك نُقل الموعد إلى السبت"
        reply += " بنفس الوقت." if due.due_time else "."
    return respond(actor, "create_task", reply, task.id)


def handle_policy(actor: Employee, message: str):
    try:
        answer = answer_policy_question(message)
    except RAGNotConfiguredError:
        logger.error("GROQ_API_KEY is missing: set it in .env")
        return error_response(503, "الخدمة غير مهيأة حاليًا. يُرجى التواصل مع مسؤول النظام.")
    except Exception:
        logger.exception("Policy answer failed")
        return error_response(502, "تعذّر الرد على سؤال السياسة الآن. يُرجى المحاولة بعد قليل.")
    return respond(actor, "policy_question", answer)


# ---------- the only endpoint ----------

@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    # The role comes from the database, never from the user's message.
    actor = db.get(Employee, payload.user_id)

    if actor is None:
        save_audit(
            db=db,
            user_id=payload.user_id,
            user_role=None,
            action="unknown_user",
        )
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")

    message = payload.message.strip()

    if not message:
        result = respond(
            actor,
            "clarification",
            "الرسالة فارغة. يرجى كتابة طلبك.",
        )

    elif re.sub(r"[^\w\s]", "", normalize_ar(message)).strip() in MY_TASKS_PHRASES:
        result = handle_list(db, actor, "mine", None)

    else:
        try:
            parsed = parse_intent(message)

        except LLMNotConfiguredError:
            logger.error("GROQ_API_KEY is missing: set it in .env")
            result = error_response(
                503,
                "الخدمة غير مهيأة حاليًا. يرجى التواصل مع مسؤول النظام.",
            )

        except Exception:
            logger.exception("Could not understand the message")
            result = error_response(
                502,
                "تعذّر فهم الرسالة الآن بسبب خلل مؤقت. يرجى المحاولة بعد قليل.",
            )

        else:
            intent, scope = parsed["intent"], parsed.get("scope")

            if intent == "unknown" and any(
                hint in normalize_ar(message) for hint in ALL_TASKS_HINTS
            ):
                intent, scope = "list_tasks", "all"

            if intent == "list_tasks":
                result = handle_list(
                    db, actor, scope or "mine", parsed.get("assignee_name")
                )

            elif intent == "policy_question":
                result = handle_policy(actor, message)

            elif intent == "create_task":
                result = handle_create(
                    db,
                    actor,
                    parsed.get("assignee_name"),
                    parsed.get("description"),
                    message,
                )

            else:
                result = respond(
                    actor,
                    "clarification",
                    "لم أفهم طلبك. يمكنني تسجيل مهمة، أو عرض مهامك، أو الإجابة عن سياسة الشركة.",
                )

    return audit_response(db, actor, result)