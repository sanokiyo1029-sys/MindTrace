"""Timed online exams with one attempt per enrollment and teacher-controlled release."""
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, FiniteFloat, StringConstraints
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import marking, serialize
from app.db import get_db
from app.errors import api_error
from app.ids import new_id
from app.models import Assessment, Assignment, ClassRoom, Exam, ExamAttempt, Student, Teacher
from app.routes.common import own_assessment
from app.security import current_enrollments, current_teacher

router = APIRouter(prefix="/api", tags=["exams"])
Text = Annotated[str, StringConstraints(max_length=5000)]
Part = Annotated[str, StringConstraints(max_length=300)]
Response = Text | Annotated[list[Part], Field(max_length=30)] | Annotated[dict[str, Part], Field(max_length=6)]


class ExamBody(BaseModel):
    assessment_id: str
    duration_minutes: int = Field(ge=1, le=180)


class SaveBody(BaseModel):
    version: int = Field(ge=1)
    answers: dict[str, Response] = Field(max_length=5)
    submit: bool = False
    write_id: UUID | None = None


class ReviewBody(BaseModel):
    version: int = Field(ge=1)
    scores: dict[str, FiniteFloat] = Field(max_length=5)
    release: bool = False


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def exam_head(exam: Exam, assessment: Assessment, classroom: ClassRoom) -> dict:
    return {"id": exam.assessment_id, "title": assessment.title, "class_id": classroom.id,
            "class_name": classroom.name, "duration_minutes": exam.duration_minutes,
            "question_count": len(exam.questions)}


def question_for_player(q: dict) -> dict:
    style = marking.style(q)
    public = {k: q[k] for k in ("id", "stem", "code", "image_url", "unit") if k in q}
    public.update(type=marking.qtype(q), style=style, marks=marking.marks(q))
    if style in ("choice", "multi"):
        public["options"] = marking.options(q)
    elif style == "blanks":
        public["blank_count"] = len(q["blanks"])
    elif style == "match":
        public["left"] = [p[0] for p in q["pairs"]]
        public["right"] = dict(zip(marking.LETTERS_EXT, marking.match_choices(q)))
    return public


def state(attempt, at):
    if attempt is None:
        return "ready"
    if attempt.released_at:
        return "released"
    if attempt.submitted_at or utc(attempt.deadline_at) <= at:
        return "submitted"
    return "in_progress"


def scores_for(exam: Exam, answers: dict, overrides: dict) -> dict:
    scores = {}
    for q in exam.questions:
        value = answers.get(q["id"])
        scores[q["id"]] = overrides.get(q["id"], marking.mark(q, value) if value else 0.0)
    return {"scores": scores, "score": round(sum(s or 0 for s in scores.values()), 2),
            "max_score": round(sum(marking.marks(q) for q in exam.questions), 2),
            "to_mark": sum(s is None for s in scores.values())}


def view(exam: Exam, attempt: ExamAttempt | None, at, *, teacher=False) -> dict:
    status = state(attempt, at)
    result = {"status": status, "server_time": at.isoformat()}
    if attempt:
        result.update(id=attempt.id, version=attempt.version, deadline_at=utc(attempt.deadline_at).isoformat())
        result["last_write_id"] = attempt.last_write_id
        if status in ("submitted", "released"):
            result["submission_reason"] = ("student" if attempt.submitted_at and
                                           utc(attempt.submitted_at) < utc(attempt.deadline_at) else "deadline")
        if status == "released" or status == ("submitted" if teacher else "in_progress"):
            result["answers"] = attempt.answers
        if status == "released" or (teacher and status == "submitted"):
            result.update(scores_for(exam, attempt.answers, attempt.teacher_scores))
        if teacher:
            result["teacher_scores"] = attempt.teacher_scores
    return result


def attempt_for(db, exam, student):
    return db.scalar(select(ExamAttempt).where(ExamAttempt.exam_id == exam.assessment_id,
                                               ExamAttempt.student_id == student.id))


def exam_for_student(db, exam_id, enrollments):
    exam = db.get(Exam, exam_id)
    assessment = db.get(Assessment, exam_id) if exam else None
    student = next((s for s in enrollments if assessment and s.class_id == assessment.class_id), None)
    if student is None:
        raise api_error(404, "not_found", "This exam isn't assigned to your class.")
    return exam, assessment, student


def player(db, exam, assessment, attempt, at):
    result = exam_head(exam, assessment, db.get(ClassRoom, assessment.class_id))
    result["attempt"] = view(exam, attempt, at)
    if result["attempt"]["status"] in ("in_progress", "released"):
        result["questions"] = [question_for_player(q) for q in exam.questions]
    return result


def validate_answers(exam, answers):
    questions = {q["id"]: q for q in exam.questions}
    kept = {}
    for qid, value in answers.items():
        if qid not in questions:
            raise api_error(400, "invalid_answer", "An answer belongs to a different exam.")
        if not value:
            continue
        q = questions[qid]
        style = marking.style(q)
        if style == "choice":
            valid = isinstance(value, str) and value in marking.options(q)
        elif style == "multi":
            valid = (isinstance(value, list) and len(set(value)) == len(value) and
                     all(item in marking.options(q) for item in value))
        elif style == "blanks":
            valid = isinstance(value, list) and len(value) <= len(q["blanks"])
            if valid and not any(item.strip() for item in value):
                continue
        elif style == "match":
            valid = isinstance(value, dict) and all(
                key in {str(i) for i in range(1, len(q["pairs"]) + 1)} and
                item in marking.LETTERS_EXT[:len(q["pairs"])] and len(item) == 1 for key, item in value.items())
        else:
            valid = isinstance(value, str)
            if valid and not value.strip():
                continue
        if not valid:
            raise api_error(400, "invalid_answer", "One answer doesn't match its question type.")
        kept[qid] = value
    return kept


@router.get("/exams")
def teacher_exams(teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    rows = db.execute(select(Exam, Assessment, ClassRoom).join(Assessment, Exam.assessment_id == Assessment.id)
                      .join(ClassRoom, Assessment.class_id == ClassRoom.id).where(ClassRoom.teacher_id == teacher.id)
                      .order_by(Exam.created_at.desc()))
    return [exam_head(*row) for row in rows]


@router.post("/exams")
def publish_exam(body: ExamBody, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    assessment = own_assessment(db, teacher, body.assessment_id, lock=True)
    existing = db.get(Exam, assessment.id)
    if existing:
        if existing.duration_minutes != body.duration_minutes:
            raise api_error(409, "exam_exists", "This exam is already published with a different duration.")
        return exam_head(existing, assessment, db.get(ClassRoom, assessment.class_id))
    if assessment.status != "approved" or db.scalar(select(Assignment.id).where(Assignment.assessment_id == assessment.id)):
        raise api_error(409, "exam_source_unavailable", "Use an approved assessment that hasn't been printed or assigned as practice.")
    questions = serialize.questions_of(db, assessment.id)
    if not questions or any(q.status != "approved" for q in questions):
        raise api_error(409, "not_approved", "Approve all questions before publishing the exam.")
    exam = Exam(assessment_id=assessment.id, duration_minutes=body.duration_minutes,
                questions=[q.data | {"id": q.id} for q in questions])
    db.add(exam)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise api_error(409, "exam_exists", "The exam was just published. Refresh the list.")
    return exam_head(exam, assessment, db.get(ClassRoom, assessment.class_id))


@router.get("/exams/{exam_id}")
def exam_report(exam_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    assessment = own_assessment(db, teacher, exam_id)
    exam = db.get(Exam, exam_id)
    if not exam:
        raise api_error(404, "not_found", "Exam not found.")
    attempts = {a.student_id: a for a in db.scalars(select(ExamAttempt).where(ExamAttempt.exam_id == exam_id))}
    roster = db.scalars(select(Student).where(Student.class_id == assessment.class_id).order_by(Student.roll_no))
    at = now()
    return {
        **exam_head(exam, assessment, db.get(ClassRoom, assessment.class_id)),
        "questions": [question_for_player(q) | {"model_answer": q.get("model_answer")} for q in exam.questions],
        "students": [{"student": serialize.student(s), "attempt": view(exam, attempts.get(s.id), at, teacher=True)}
                     for s in roster],
    }


@router.patch("/exams/{exam_id}/attempts/{attempt_id}")
def review_exam(exam_id: str, attempt_id: str, body: ReviewBody,
                teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    own_assessment(db, teacher, exam_id)
    exam, attempt = db.get(Exam, exam_id), db.get(ExamAttempt, attempt_id)
    if not exam or not attempt or attempt.exam_id != exam_id:
        raise api_error(404, "not_found", "Exam submission not found.")
    at = now()
    status = state(attempt, at)
    if status == "released":
        return view(exam, attempt, at, teacher=True)
    if status != "submitted":
        raise api_error(409, "not_submitted", "Wait for the student to submit or for their timer to end.")
    limits = {q["id"]: marking.marks(q) for q in exam.questions}
    if any(qid not in limits or not 0 <= score <= limits[qid] for qid, score in body.scores.items()):
        raise api_error(400, "invalid_score", "Each mark must be between zero and the question's maximum.")
    marks = attempt.teacher_scores | body.scores
    if body.release and scores_for(exam, attempt.answers, marks)["to_mark"]:
        raise api_error(409, "marks_required", "Mark all written answers before releasing this result.")
    changed = db.execute(update(ExamAttempt).where(ExamAttempt.id == attempt_id, ExamAttempt.version == body.version,
                                                   ExamAttempt.released_at.is_(None))
                         .values(teacher_scores=marks, released_at=at if body.release else None,
                                 submitted_at=attempt.submitted_at or attempt.deadline_at, version=ExamAttempt.version + 1)
                         .execution_options(synchronize_session=False))
    db.commit()
    if not changed.rowcount:
        raise api_error(409, "conflict", "This result changed. Refresh the report before marking again.")
    db.refresh(attempt)
    return view(exam, attempt, at, teacher=True)


@router.get("/student/me/exams")
def my_exams(enrollments: list[Student] = Depends(current_enrollments), db: Session = Depends(get_db)):
    ids = {s.class_id: s.id for s in enrollments}
    attempts = {(a.exam_id, a.student_id): a for a in db.scalars(
        select(ExamAttempt).where(ExamAttempt.student_id.in_(ids.values())))}
    rows = db.execute(select(Exam, Assessment, ClassRoom).join(Assessment, Exam.assessment_id == Assessment.id)
                      .join(ClassRoom, Assessment.class_id == ClassRoom.id).where(ClassRoom.id.in_(ids))
                      .order_by(Exam.created_at.desc()))
    at = now()
    return [{**exam_head(exam, a, cls),
             "status": state(attempts.get((exam.assessment_id, ids[cls.id])), at)}
            for exam, a, cls in rows]


@router.get("/student/me/exams/{exam_id}")
def my_exam(exam_id: str, enrollments: list[Student] = Depends(current_enrollments), db: Session = Depends(get_db)):
    exam, assessment, student = exam_for_student(db, exam_id, enrollments)
    return player(db, exam, assessment, attempt_for(db, exam, student), now())


@router.post("/student/me/exams/{exam_id}/start")
def start_exam(exam_id: str, enrollments: list[Student] = Depends(current_enrollments), db: Session = Depends(get_db)):
    exam, assessment, student = exam_for_student(db, exam_id, enrollments)
    attempt, at = attempt_for(db, exam, student), now()
    if attempt is None:
        attempt = ExamAttempt(id=new_id("exa"), exam_id=exam_id, student_id=student.id, started_at=at,
                              deadline_at=at + timedelta(minutes=exam.duration_minutes))
        db.add(attempt)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            attempt = attempt_for(db, exam, student)
            if attempt is None:
                raise api_error(409, "exam_unavailable", "Couldn't start this exam. Refresh and try again.") from None
    return player(db, exam, assessment, attempt, at)


@router.put("/student/me/exams/{exam_id}/attempt")
def save_attempt(exam_id: str, body: SaveBody, enrollments: list[Student] = Depends(current_enrollments),
                 db: Session = Depends(get_db)):
    exam, assessment, student = exam_for_student(db, exam_id, enrollments)
    attempt, at = attempt_for(db, exam, student), now()
    if attempt is None:
        raise api_error(409, "not_started", "Start the exam before sending answers.")
    write_id = str(body.write_id) if body.write_id else None
    if state(attempt, at) != "in_progress" or (write_id and attempt.last_write_id == write_id):
        return player(db, exam, assessment, attempt, at)
    answers = validate_answers(exam, body.answers)
    changed = db.execute(update(ExamAttempt).where(ExamAttempt.id == attempt.id, ExamAttempt.version == body.version,
                                                   ExamAttempt.submitted_at.is_(None), ExamAttempt.deadline_at > at)
                         .values(answers=answers, submitted_at=at if body.submit else None, last_write_id=write_id,
                                 version=ExamAttempt.version + 1)
                         .execution_options(synchronize_session=False))
    db.commit()
    db.refresh(attempt)
    at = now()
    current = player(db, exam, assessment, attempt, at)
    if not changed.rowcount and current["attempt"]["status"] == "in_progress" and (not write_id or attempt.last_write_id != write_id):
        raise api_error(409, "conflict", "This attempt changed in another tab. Check the saved answers.",
                        current=current)
    return current
