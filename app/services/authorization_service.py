"""All permission rules live here, in code. The LLM never decides who can do what.

The actor always comes from the database (by user_id). Nothing in the message text can change the role.
  employee   -> own tasks only
  supervisor -> own department
  manager    -> everyone
"""
from sqlalchemy import select
from sqlalchemy.orm import Query, Session

from app.models import Employee, Task


class AuthorizationError(Exception):
    """The message is a clear Arabic reason that can be sent to the user."""


def can_access(actor: Employee, target: Employee) -> bool:
    """Same rule for 'assign a task to target' and 'see target's tasks'."""
    if actor.role == "manager" or actor.id == target.id:
        return True
    return actor.role == "supervisor" and actor.department == target.department


def check_can_assign(actor: Employee, target: Employee) -> None:
    if can_access(actor, target):
        return
    if actor.role == "supervisor":
        raise AuthorizationError(
            f"لا يمكنك إسناد مهمة إلى {target.name} لأنه من قسم آخر. المشرف يسند المهام لموظفي قسمه فقط."
        )
    raise AuthorizationError("لا يمكنك إسناد مهام للآخرين. الموظف يسجّل المهام لنفسه فقط.")


def tasks_for_scope(db: Session, actor: Employee, scope: str, target: Employee | None = None) -> Query:
    """Return the tasks this actor may see. Raise AuthorizationError if the scope is not allowed."""
    query = db.query(Task)

    if scope == "mine":
        return query.filter(Task.assigned_to == actor.id)

    if scope == "all":
        if actor.role != "manager":
            raise AuthorizationError(
                "عرض مهام الشركة كلها متاح للمدير فقط. صلاحيتك تُقرأ من النظام وليس من الرسالة."
            )
        return query

    if scope == "department":
        if actor.role == "manager":
            return query
        if actor.role == "supervisor":
            same_department = select(Employee.id).where(Employee.department == actor.department)
            return query.filter(Task.assigned_to.in_(same_department))
        raise AuthorizationError("عرض مهام القسم متاح للمشرف أو المدير فقط.")

    if scope == "person" and target is not None:
        if not can_access(actor, target):
            raise AuthorizationError(
                f"لا يمكنك عرض مهام {target.name}. الموظف يرى مهامه فقط، والمشرف يرى مهام قسمه، والمدير يرى الجميع."
            )
        return query.filter(Task.assigned_to == target.id)

    raise ValueError(f"Unknown scope: {scope}")
