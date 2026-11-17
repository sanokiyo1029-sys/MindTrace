from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import serialize
from app.db import get_db
from app.errors import api_error
from app.models import Student, Teacher
from app.security import check_secret, issue_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TeacherLogin(BaseModel):
    email: str
    password: str


class StudentLogin(BaseModel):
    student_code: str
    pin: str


@router.post("/teacher/login")
def teacher_login(body: TeacherLogin, db: Session = Depends(get_db)):
    t = db.scalar(select(Teacher).where(Teacher.email == body.email.strip().lower()))
    if not t or not check_secret(body.password, t.password_hash):
        raise api_error(401, "bad_login", "Wrong email or password.")
    return {"token": issue_token(db, "teacher", t.id), "teacher": {"id": t.id, "name": t.name, "email": t.email}}


@router.post("/student/login")
def student_login(body: StudentLogin, db: Session = Depends(get_db)):
    s = db.scalar(select(Student).where(Student.student_code == body.student_code.strip().upper()))
    if not s or not check_secret(body.pin.strip(), s.pin_hash):
        raise api_error(401, "bad_login", "Wrong student code or PIN.")
    return {"token": issue_token(db, "student", s.id), "student": serialize.student(s)}
