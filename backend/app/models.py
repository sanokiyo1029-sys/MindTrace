"""Tables. Shapes returned by the API are built in app/serialize.py to match docs/CONTRACTS.md."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now():
    return datetime.now(timezone.utc)


class Teacher(Base):
    __tablename__ = "teachers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)


class ClassRoom(Base):
    __tablename__ = "classes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"))
    name: Mapped[str] = mapped_column(String)          # e.g. "7A"
    grade: Mapped[str] = mapped_column(String, default="7")


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("class_id", "roll_no", name="ux_students_class_roll"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    display_name: Mapped[str] = mapped_column(String)
    student_code: Mapped[str] = mapped_column(String, unique=True)  # login ID, unique school-wide ("7A-01")
    # What the student writes at the top of the paper. A string (keeps leading zeros, allows "12B");
    # unique within a class only, so two classes can both have roll "01".
    roll_no: Mapped[str | None] = mapped_column(String, nullable=True)
    pin_hash: Mapped[str] = mapped_column(String)


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    title: Mapped[str] = mapped_column(String)
    topic: Mapped[str] = mapped_column(String)
    concepts_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="draft")  # draft|approved|printed|scanning|confirmed
    parent_assessment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[list] = mapped_column(JSON, default=list)        # e.g. ["Using saved sample questions (AI unavailable)"]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    position: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)   # full Question dict (CONTRACTS §2) minus id/assessment_id/status
    status: Mapped[str] = mapped_column(String, default="draft")


class Sheet(Base):
    __tablename__ = "sheets"
    sheet_id: Mapped[str] = mapped_column(String, primary_key=True)
    short_code: Mapped[str] = mapped_column(String)  # "MT-001", unique within an assessment
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))


class Scan(Base):
    __tablename__ = "scans"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    sheet_id: Mapped[str | None] = mapped_column(String, nullable=True)  # set once the student is known
    status: Mapped[str] = mapped_column(String)            # accepted|needs_review|duplicate|rejected
    reject_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    answers: Mapped[list] = mapped_column(JSON, default=list)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    duplicate_of: Mapped[str | None] = mapped_column(String, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)  # the one live scan per student
    roll_number: Mapped[str | None] = mapped_column(String, nullable=True)  # as written on the paper (or typed)
    extracted_by: Mapped[str | None] = mapped_column(String, nullable=True)  # gemini|bubble_reader|manual|qr_legacy
    identity: Mapped[dict | None] = mapped_column(JSON, nullable=True)      # {status, candidates}
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)      # [{code, message}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuthToken(Base):
    __tablename__ = "tokens"
    token: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String)              # teacher|student
    subject_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
