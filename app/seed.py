from app.database import Base, engine, SessionLocal
from app.models import Employee

EMPLOYEES = [
    (1, "منيرة", "manager", "admin"),
    (2, "سارة", "supervisor", "projects"),
    (3, "فهد", "employee", "projects"),
    (4, "خالد", "employee", "projects"),
    (5, "نورة", "employee", "finance"),
    (6, "عبدالرحمن", "supervisor", "finance"),
]


def initialize_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        for emp_id, name, role, department in EMPLOYEES:
            employee = db.get(Employee, emp_id)

            if employee is None:
                employee = Employee(
                    id=emp_id,
                    name=name,
                    role=role,
                    department=department,
                )
                db.add(employee)
            else:
                employee.name = name
                employee.role = role
                employee.department = department

        db.commit()
    finally:
        db.close()
