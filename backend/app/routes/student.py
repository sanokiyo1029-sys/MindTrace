"""The signed-in student's own work only. Every query starts from the student's id; there is no way to ask for
another student's results, scans or practice."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import ai_bridge, marking, serialize
from app.db import get_db
from app.errors import api_error
from app.ids import new_id
from app.models import Assessment, Assignment, AuthToken, Feedback, PracticeSubmission, Scan, Sheet, Student, StudentAccount
from app.routes.assessments import score
from app.security import current_enrollments, current_session

router = APIRouter(prefix="/api/student", tags=["student"])


def released(a: Assessment, sc: Scan | None) -> bool:
    """A student sees a paper once the teacher confirmed it AND locked the assessment's results."""
    return bool(sc) and sc.status == "accepted" and a.status == "confirmed"


@router.get("/me/results")
def my_results(enrollments: list[Student] = Depends(current_enrollments), session: AuthToken = Depends(current_session),
               db: Session = Depends(get_db)):
    """CONTRACTS section 9, plus (additive) status, score, scan image, approved feedback and dates. Covers every class
    the student (account) is enrolled in."""
    lib = ai_bridge.misconception_library()
    out = []
    ids = [s.id for s in enrollments]
    for sh in db.scalars(select(Sheet).where(Sheet.student_id.in_(ids))):
        a = db.get(Assessment, sh.assessment_id)
        sc = db.scalar(select(Scan).where(Scan.sheet_id == sh.sheet_id, Scan.is_current.is_(True)))
        head = {"assessment_id": a.id, "title": a.title, "topic": a.topic, "subject": a.subject or "mathematics",
                "created_at": a.created_at.isoformat()}
        if not released(a, sc):
            if sc and sc.status in ("needs_review", "accepted"):
                out.append({**head, "status": "awaiting_review", "answers": []})
            continue
        qs = {q.id: q.data for q in serialize.questions_of(db, a.id)}
        plan = a.plan or {}
        answers = []
        for x in sc.answers:
            q = qs.get(x["question_id"])
            if not q:
                continue
            chosen = x.get("final")
            maybe = None
            if not marking.written(q) and chosen in ("A", "B", "C", "D") and chosen != q["answer"]:
                mid = ((q.get("distractors") or {}).get(chosen) or {}).get("misconception_id")
                maybe = lib.get(mid, {}).get("student_friendly")
            answers.append({"question_id": x["question_id"], "type": q.get("type", "mcq"), "stem": q["stem"],
                            "written": marking.written(q),
                            "options": marking.options(q) or None, "chosen": chosen, "correct": q.get("answer"),
                            "explanation": q.get("explanation"), "maybe": maybe, "text": x.get("text", ""),
                            "concept": q.get("concept", ""), "code": q.get("code"), "image_url": q.get("image_url"),
                            **{k: v for k, v in marking.scored(q, x).items() if k in ("score", "max_score")}})
        feedback = []
        for f in db.scalars(select(Feedback).where(Feedback.scan_id == sc.id, Feedback.status == "approved")):
            mid = (f.suggestion or {}).get("misconception_id")
            step = plan.get(mid) or {}
            video = f.video_url or (step.get("video_url") if step.get("status") != "dismissed" else None)
            feedback.append({"question_id": f.question_id, "concept": f.concept, "text": f.text, "video_url": video})
        correct, total = score(qs, sc.answers)
        out.append({**head, "status": "released", "answers": answers, "score": {"correct": correct, "total": total,
                                                                               **marking.totals(qs, sc.answers)},
                    "scan_url": sc.image_url, "feedback": feedback})
    out.sort(key=lambda r: r["created_at"], reverse=True)
    acc = db.get(StudentAccount, session.subject_id)
    return {"student": {"display_name": acc.name if acc else enrollments[0].display_name}, "assessments": out}


def _practice_item(db: Session, asg: Assignment, student: Student) -> dict:
    a = db.get(Assessment, asg.assessment_id)
    qs = serialize.questions_of(db, a.id)
    sub = db.scalar(select(PracticeSubmission).where(PracticeSubmission.assignment_id == asg.id,
                                                     PracticeSubmission.student_id == student.id))
    item = {"assignment_id": asg.id, "title": a.title, "topic": a.topic, "subject": a.subject or "mathematics",
            "assigned_at": asg.created_at.isoformat(), "status": "submitted" if sub else "not_started",
            # no answer key until the student has submitted
            "questions": [{"id": q.id, "type": q.data.get("type", "mcq"), "stem": q.data["stem"],
                           "options": marking.options(q.data) or None, "written": marking.written(q.data),
                           "hint": marking.paper_lines(q.data), "code": q.data.get("code"),
                           "image_url": q.data.get("image_url"), "max_score": marking.marks(q.data)} for q in qs]}
    if sub:
        given = {x["question_id"]: x for x in sub.answers}
        item["submitted_at"] = sub.created_at.isoformat()
        item["result"] = [{"question_id": q.id, "chosen": given.get(q.id, {}).get("choice"),
                           "text": given.get(q.id, {}).get("text"), "correct": q.data.get("answer"),
                           "explanation": q.data.get("explanation"),
                           "score": marking.mark(q.data, given[q.id].get("text") if marking.written(q.data)
                                                 else given[q.id].get("choice")) if q.id in given else 0.0,
                           "max_score": marking.marks(q.data)} for q in qs]
    return item


@router.get("/me/practice")
def my_practice(enrollments: list[Student] = Depends(current_enrollments), db: Session = Depends(get_db)):
    by_class = {s.class_id: s for s in enrollments}
    rows = db.scalars(select(Assignment).where(Assignment.class_id.in_(list(by_class))).order_by(Assignment.created_at.desc()))
    return [_practice_item(db, asg, by_class[asg.class_id]) for asg in rows]


class PracticeAnswer(BaseModel):
    question_id: str
    choice: str | None = Field(None, pattern="^[ABCD]$")
    text: str | None = Field(None, max_length=4000)


class PracticeBody(BaseModel):
    answers: list[PracticeAnswer]


@router.post("/me/practice/{assignment_id}")
def submit_practice(assignment_id: str, body: PracticeBody, enrollments: list[Student] = Depends(current_enrollments),
                    db: Session = Depends(get_db)):
    """Once per student. A repeated submit (double tap, offline retry) returns the first one unchanged."""
    asg = db.get(Assignment, assignment_id)
    student = next((s for s in enrollments if asg and s.class_id == asg.class_id), None)
    if not asg or student is None:
        raise api_error(404, "not_found", "That practice isn't assigned to you.")
    existing = db.scalar(select(PracticeSubmission).where(PracticeSubmission.assignment_id == asg.id,
                                                          PracticeSubmission.student_id == student.id))
    if not existing:
        qids = {q.id for q in serialize.questions_of(db, asg.assessment_id)}
        answers = [x.model_dump() for x in body.answers if x.question_id in qids]
        if not answers:
            raise api_error(400, "empty_submission", "Answer at least one question before submitting.")
        db.add(PracticeSubmission(id=new_id("ps"), assignment_id=asg.id, student_id=student.id, answers=answers))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        return _practice_item(db, asg, student)
    return {**_practice_item(db, asg, student), "already_submitted": True}
