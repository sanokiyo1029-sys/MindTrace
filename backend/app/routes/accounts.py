"""Accounts: student self-registration with a class join code, joining more classes, password recovery and profiles.

Student accounts (email + password) sit next to the original student code + PIN logins, which keep working. Each class
a student account joins is a normal `students` row with its own roll number, so paper scanning is unchanged."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import mailer, rolls, serialize
from app.db import get_db
from app.errors import api_error
from app.ids import new_id
from app.models import AuthToken, ClassRoom, PasswordReset, Student, StudentAccount, Teacher
from app.security import (check_secret, check_throttle, clear_failures, current_enrollments, current_session,
                          end_sessions, hash_secret, issue_token, record_failure)

router = APIRouter(prefix="/api", tags=["accounts"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
RESET_MINUTES = 30


def password_problem(pw: str) -> str | None:
    if len(pw) < 8 or pw.isdigit() or pw.isalpha():
        return "Use at least 8 characters, with letters and numbers."
    return None


def _clean_email(email: str) -> str:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise api_error(400, "bad_email", "Enter a valid email address.")
    return email


def _clean_roll(roll: str) -> str:
    r = rolls.normalize(roll)
    if not re.fullmatch(r"[A-Z0-9]{1,12}", r or ""):
        raise api_error(400, "bad_roll", "Enter your roll number as it appears on class papers, e.g. 07.")
    return r


def email_taken(db: Session, email: str) -> bool:
    return bool(db.scalar(select(Teacher).where(Teacher.email == email)) or
                db.scalar(select(StudentAccount).where(StudentAccount.email == email)))


def new_student_code(db: Session, cls: ClassRoom, roll: str) -> str:
    base = re.sub(r"[^A-Z0-9]", "", cls.name.upper())[:6] or "S"
    code = f"{base}-{roll}"
    while db.scalar(select(Student).where(Student.student_code == code)):
        code = f"{base}-{roll}-{secrets.token_hex(2).upper()}"
    return code


def enroll(db: Session, cls: ClassRoom, name: str, roll: str, account_id: str | None = None) -> tuple[Student, str]:
    """Add a student to a class. Returns (student, PIN). The PIN is shown once (the teacher hands it out)."""
    if db.scalar(select(Student).where(Student.class_id == cls.id, Student.roll_no == roll)):
        raise api_error(409, "roll_taken", f"Roll number {roll} is already taken in class {cls.name}. "
                                           "Check your roll number, or ask your teacher.")
    pin = f"{secrets.randbelow(10000):04d}"
    s = Student(id=new_id("st"), class_id=cls.id, display_name=name, student_code=new_student_code(db, cls, roll),
                roll_no=roll, pin_hash=hash_secret(pin), account_id=account_id)
    db.add(s)
    return s, pin


def class_by_code(db: Session, code: str) -> ClassRoom:
    cls = db.scalar(select(ClassRoom).where(ClassRoom.join_code == code.strip().upper()))
    if not cls:
        raise api_error(404, "bad_class_code", "That class code wasn't found. Check it with your teacher.")
    return cls


# ---------------------------------------------------------------- student sign-up and classes
class StudentSignup(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)
    class_code: str = Field(max_length=20)
    roll_no: str = Field(max_length=20)


@router.post("/auth/student/signup")
def student_signup(body: StudentSignup, db: Session = Depends(get_db)):
    name, email = " ".join(body.name.split()), _clean_email(body.email)
    if not name:
        raise api_error(400, "bad_name", "Enter your name.")
    if problem := password_problem(body.password):
        raise api_error(400, "weak_password", problem)
    cls, roll = class_by_code(db, body.class_code), _clean_roll(body.roll_no)
    if email_taken(db, email):
        raise api_error(409, "email_taken", "An account with this email already exists. Sign in instead.")
    acc = StudentAccount(id=new_id("sa"), email=email, name=name, password_hash=hash_secret(body.password))
    db.add(acc)
    db.flush()
    enroll(db, cls, name, roll, acc.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise api_error(409, "email_taken", "An account with this email already exists. Sign in instead.") from None
    return {"token": issue_token(db, "student", acc.id), "student": {"id": acc.id, "name": acc.name, "email": acc.email}}


def account_login(db: Session, email: str, password: str):
    key = f"student:{email.strip().lower()}"
    check_throttle(key)
    acc = db.scalar(select(StudentAccount).where(StudentAccount.email == email.strip().lower()))
    if not acc or not check_secret(password, acc.password_hash):
        record_failure(key)
        raise api_error(401, "bad_login", "Wrong email or password.")
    clear_failures(key)
    return {"token": issue_token(db, "student", acc.id), "student": {"id": acc.id, "name": acc.name, "email": acc.email}}


class JoinClass(BaseModel):
    class_code: str = Field(max_length=20)
    roll_no: str = Field(max_length=20)


@router.get("/student/classes")
def my_classes(enrollments: list[Student] = Depends(current_enrollments), db: Session = Depends(get_db)):
    out = []
    for s in enrollments:
        c = db.get(ClassRoom, s.class_id)
        t = db.get(Teacher, c.teacher_id)
        out.append({"class_id": c.id, "name": c.name, "grade": c.grade, "teacher": t.name, "roll_no": s.roll_no,
                    "student_code": s.student_code})
    return out


@router.post("/student/classes/join")
def join_class(body: JoinClass, session: AuthToken = Depends(current_session),
               enrollments: list[Student] = Depends(current_enrollments), db: Session = Depends(get_db)):
    acc = db.get(StudentAccount, session.subject_id)
    if not acc:
        raise api_error(403, "account_required", "Create a student account (email and password) to join more classes.")
    cls, roll = class_by_code(db, body.class_code), _clean_roll(body.roll_no)
    if any(s.class_id == cls.id for s in enrollments):
        raise api_error(409, "already_joined", f"You're already in class {cls.name}.")
    enroll(db, cls, acc.name, roll, acc.id)
    db.commit()
    return my_classes(list(db.scalars(select(Student).where(Student.account_id == acc.id))), db)


# ---------------------------------------------------------------- password recovery
def make_reset(db: Session, kind: str, subject_id: str) -> str:
    token = secrets.token_urlsafe(32)
    db.add(PasswordReset(token_hash=hashlib.sha256(token.encode()).hexdigest(), kind=kind, subject_id=subject_id,
                         expires_at=datetime.now(timezone.utc) + timedelta(minutes=RESET_MINUTES)))
    db.commit()
    return token


class Forgot(BaseModel):
    email: str = Field(max_length=254)


@router.post("/auth/password/forgot")
def forgot_password(body: Forgot, db: Session = Depends(get_db)):
    """Always the same answer, whether or not the email has an account (no account discovery)."""
    email = body.email.strip().lower()
    check_throttle(f"forgot:{email}")
    record_failure(f"forgot:{email}")  # at most 5 reset emails per address per 10 minutes
    if mailer.enabled():
        t = db.scalar(select(Teacher).where(Teacher.email == email))
        acc = None if t else db.scalar(select(StudentAccount).where(StudentAccount.email == email))
        if t or acc:
            token = make_reset(db, "teacher" if t else "student_account", (t or acc).id)
            from app import config
            mailer.send(email, "Reset your MindTrace password",
                        f"Someone asked to reset the password for this MindTrace account.\n\n"
                        f"Open this link within {RESET_MINUTES} minutes to choose a new password:\n"
                        f"{config.PUBLIC_URL}/reset-password#token={token}\n\nIf it wasn't you, ignore this email.")
    return {"ok": True, "email_enabled": mailer.enabled()}


class Reset(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(max_length=200)


@router.post("/auth/password/reset")
def reset_password(body: Reset, db: Session = Depends(get_db)):
    row = db.get(PasswordReset, hashlib.sha256(body.token.encode()).hexdigest())
    expires = row.expires_at if row and row.expires_at.tzinfo else (row.expires_at.replace(tzinfo=timezone.utc) if row else None)
    if not row or row.used or expires < datetime.now(timezone.utc):
        raise api_error(400, "bad_reset_link", "This reset link has expired or was already used. Ask for a new one.")
    if problem := password_problem(body.password):
        raise api_error(400, "weak_password", problem)
    who = db.get(Teacher if row.kind == "teacher" else StudentAccount, row.subject_id)
    who.password_hash = hash_secret(body.password)
    row.used = True
    end_sessions(db, who.id)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- profile
def _profile(db: Session, session: AuthToken) -> dict:
    if session.role == "teacher":
        t = db.get(Teacher, session.subject_id)
        return {"role": "teacher", "name": t.name, "email": t.email, "has_password": True,
                "google_linked": bool(t.google_sub)}
    acc = db.get(StudentAccount, session.subject_id)
    if acc:
        return {"role": "student", "name": acc.name, "email": acc.email, "has_password": True, "google_linked": False}
    s = db.get(Student, session.subject_id)
    return {"role": "student", "name": s.display_name, "email": None, "has_password": False,
            "google_linked": bool(s.google_sub), "student_code": s.student_code}


@router.get("/auth/profile")
def get_profile(session: AuthToken = Depends(current_session), db: Session = Depends(get_db)):
    return _profile(db, session)


class ProfileEdit(BaseModel):
    name: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=254)
    current_password: str | None = Field(None, max_length=200)
    new_password: str | None = Field(None, max_length=200)


@router.patch("/auth/profile")
def edit_profile(body: ProfileEdit, session: AuthToken = Depends(current_session), db: Session = Depends(get_db)):
    """Name: any signed-in person. Email or password: needs the current password (code + PIN students have none)."""
    who = db.get(Teacher, session.subject_id) if session.role == "teacher" else db.get(StudentAccount, session.subject_id)
    if who is None:  # old-style code + PIN student
        if body.email or body.new_password:
            raise api_error(403, "account_required", "Ask your teacher to change your PIN, or create a student account.")
        s = db.get(Student, session.subject_id)
        if body.name and body.name.strip():
            s.display_name = " ".join(body.name.split())
        db.commit()
        return _profile(db, session)
    if body.name is not None:
        name = " ".join(body.name.split())
        if not name:
            raise api_error(400, "bad_name", "Enter your name.")
        who.name = name
        if isinstance(who, StudentAccount):  # keep the class lists in step
            for s in db.scalars(select(Student).where(Student.account_id == who.id)):
                s.display_name = name
    if body.email or body.new_password:
        if not body.current_password or not check_secret(body.current_password, who.password_hash):
            raise api_error(403, "wrong_password", "Enter your current password to change your email or password.")
    if body.email:
        email = _clean_email(body.email)
        if email != who.email and email_taken(db, email):
            raise api_error(409, "email_taken", "Another account already uses this email.")
        who.email = email
    if body.new_password:
        if problem := password_problem(body.new_password):
            raise api_error(400, "weak_password", problem)
        who.password_hash = hash_secret(body.new_password)
        # sign out every other session; keep this one
        db.query(AuthToken).filter(AuthToken.subject_id == who.id, AuthToken.token != session.token).delete()
    db.commit()
    return _profile(db, session)
