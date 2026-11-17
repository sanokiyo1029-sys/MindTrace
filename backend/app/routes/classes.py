from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import serialize
from app.db import get_db
from app.errors import api_error
from app.models import ClassRoom, Student, Teacher
from app.security import current_teacher

router = APIRouter(prefix="/api/classes", tags=["classes"])


@router.get("")
def list_classes(teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    rows = db.scalars(select(ClassRoom).where(ClassRoom.teacher_id == teacher.id))
    return [{"id": c.id, "name": c.name, "grade": c.grade} for c in rows]


@router.get("/{class_id}/students")
def list_students(class_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    c = db.get(ClassRoom, class_id)
    if not c or c.teacher_id != teacher.id:
        raise api_error(404, "not_found", "Class not found.")
    rows = db.scalars(select(Student).where(Student.class_id == class_id).order_by(Student.student_code))
    return [serialize.student(s) for s in rows]
