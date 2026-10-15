from sqlalchemy.orm import Session

from app.models import Employee, Task
from app.services.authorization_service import check_can_assign
from app.services.date_service import Due, parse_due
from app.services.text_utils import normalize_ar


class NeedsClarification(Exception):
    """The request is not clear. The message is the question to ask the user."""


def find_employee(db: Session, name: str | None) -> Employee | None:
    """Exact match on the stored name (after Arabic normalization). Never guess."""
    if not name:
        return None

    wanted = normalize_ar(name).replace(" ", "")
    candidates = [wanted]

    if wanted.startswith("ل"):
        candidates.append(wanted[1:])

    employees = db.query(Employee).all()

    for candidate in candidates:
        for employee in employees:
            stored_name = normalize_ar(employee.name).replace(" ", "")
            if stored_name == candidate:
                return employee

    return None



def create_task(
    db: Session,
    actor: Employee,
    assignee: Employee,
    description: str | None,
    message: str,
) -> tuple[Task, Due]:
    # Authorization must happen in code, before writing to the database.
    check_can_assign(actor, assignee)

    if not description or not description.strip():
        raise NeedsClarification("ما هي المهمة المطلوب تسجيلها؟")

    clean_description = " ".join(description.split()).casefold()

    due = parse_due(message)

    if due.time_ambiguous:
        raise NeedsClarification(
            "ذكرت أكثر من موعد في الرسالة. "
            "ما الوقت الذي تريد تسجيل المهمة فيه؟"
        )

    if due.time_mentioned and due.due_time is None:
        raise NeedsClarification(
            "لم أفهم الوقت المطلوب. "
            "يُرجى تحديد الساعة بوضوح، مثل 10:00."
        )

    if due.due_time and not due.due_date:
        raise NeedsClarification(
            "ما اليوم المطلوب لهذا الموعد؟"
        )

    # Check for an identical pending task before inserting a new record.
    existing_tasks = (
        db.query(Task)
        .filter(
            Task.assigned_to == assignee.id,
            Task.due_date == due.due_date,
            Task.due_time == due.due_time,
            Task.status == "pending",
        )
        .all()
    )

    for existing in existing_tasks:
        existing_description = " ".join(
            (existing.description or "").split()
        ).casefold()

        if existing_description == clean_description:
            raise NeedsClarification(
                "المهمة دي مسجلة بالفعل لنفس الموظف وبنفس الموعد، "
                "فما أضفتش نسخة مكررة."
            )

    task = Task(
        description=" ".join(description.split()),
        created_by=actor.id,
        assigned_to=assignee.id,
        due_date=due.due_date,
        due_time=due.due_time,
        status="pending",
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task, due
