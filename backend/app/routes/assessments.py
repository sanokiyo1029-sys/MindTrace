from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ai_bridge, insights, serialize
from app.db import get_db
from app.errors import api_error
from app.ids import new_id
from app.models import Assessment, ClassRoom, Question, Sheet, Student, Teacher
from app.pdf import build_pdf
from app.routes.common import current_scans, own_assessment, sheets_of
from app.security import current_teacher

router = APIRouter(prefix="/api", tags=["assessments"])

EDITABLE = {"stem", "options", "answer", "explanation", "distractors", "difficulty", "concept"}
LOCKED = {"printed", "scanning", "confirmed"}


def _with_errors(qd: dict) -> dict:
    qd["validation_errors"] = ai_bridge.validate_question(qd)
    return qd


def _assessment_out(db: Session, a: Assessment) -> dict:
    out = serialize.assessment(db, a)
    out["questions"] = [_with_errors(q) for q in out["questions"]]
    return out


def _store_questions(db: Session, a: Assessment, qs: list[dict]):
    for i, q in enumerate(qs):
        data = {k: v for k, v in q.items() if k not in ("id", "assessment_id", "status", "validation_errors")}
        data.setdefault("topic", a.topic)
        db.add(Question(id=new_id("q"), assessment_id=a.id, position=i, data=data, status="draft"))


# ---------------------------------------------------------------- list / get
@router.get("/assessments")
def list_assessments(teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    class_ids = [c.id for c in db.scalars(select(ClassRoom).where(ClassRoom.teacher_id == teacher.id))]
    rows = db.scalars(select(Assessment).where(Assessment.class_id.in_(class_ids)).order_by(Assessment.created_at.desc()))
    return [{"id": a.id, "title": a.title, "topic": a.topic, "status": a.status, "class_id": a.class_id,
             "parent_assessment_id": a.parent_assessment_id, "created_at": a.created_at.isoformat()} for a in rows]


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    return _assessment_out(db, own_assessment(db, teacher, assessment_id))


# ---------------------------------------------------------------- generate
class GenerateBody(BaseModel):
    class_id: str
    topic: str = "fractions"
    concepts_text: str = ""
    num_questions: int = Field(3, ge=1, le=5)
    title: str | None = None


@router.post("/assessments/generate")
def generate(body: GenerateBody, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    cls = db.get(ClassRoom, body.class_id)
    if not cls or cls.teacher_id != teacher.id:
        raise api_error(404, "not_found", "Class not found.")
    qs, note = ai_bridge.generate_questions(body.topic, body.concepts_text, body.num_questions, cls.grade)
    a = Assessment(id=new_id("as"), class_id=cls.id, title=body.title or f"{body.topic.title()} check",
                   topic=body.topic, concepts_text=body.concepts_text, status="draft", notes=[note] if note else [])
    db.add(a)
    db.flush()
    _store_questions(db, a, qs[: body.num_questions])
    db.commit()
    return _assessment_out(db, a)


# ---------------------------------------------------------------- edit / approve
@router.patch("/questions/{question_id}")
def edit_question(question_id: str, body: dict, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise api_error(404, "not_found", "Question not found.")
    a = own_assessment(db, teacher, q.assessment_id)
    if a.status in LOCKED:
        raise api_error(409, "already_printed", "This quiz is already printed. Create a new one to change questions.")
    data = dict(q.data)
    for k, v in body.items():
        if k in EDITABLE:
            data[k] = v
    data["edited_by_teacher"] = True
    q.data = data
    q.status = "draft"
    a.status = "draft"  # any edit needs a fresh approval
    db.commit()
    return _with_errors(serialize.question(q))


@router.post("/assessments/{assessment_id}/approve")
def approve(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    a = own_assessment(db, teacher, assessment_id)
    if a.status in LOCKED:
        return _assessment_out(db, a)
    qs = serialize.questions_of(db, a.id)
    if not qs:
        raise api_error(400, "no_questions", "Add at least one question first.")
    problems = {q.id: errs for q in qs if (errs := ai_bridge.validate_question(q.data))}
    if problems:
        raise api_error(400, "invalid_questions", "Fix the highlighted questions before approving.", questions=problems)
    for q in qs:
        q.status = "approved"
    a.status = "approved"
    db.commit()
    return _assessment_out(db, a)


# ---------------------------------------------------------------- print
@router.get("/assessments/{assessment_id}/print")
def print_sheets(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    a = own_assessment(db, teacher, assessment_id)
    if a.status == "draft":
        raise api_error(409, "not_approved", "Approve all questions before printing.")
    cls = db.get(ClassRoom, a.class_id)
    students = list(db.scalars(select(Student).where(Student.class_id == a.class_id).order_by(Student.student_code)))
    existing = {s.student_id for s in sheets_of(db, a.id)}
    n = len(existing)
    for stu in students:
        if stu.id not in existing:
            n += 1
            db.add(Sheet(sheet_id=new_id("s", 10), short_code=f"MT-{n:03d}", assessment_id=a.id, student_id=stu.id))
    if a.status == "approved":
        a.status = "printed"
    db.commit()
    by_id = {s.id: s for s in students}
    sheets = [{"sheet_id": sh.sheet_id, "short_code": sh.short_code,
               "student_name": by_id[sh.student_id].display_name if sh.student_id in by_id else "",
               "class_name": cls.name} for sh in sheets_of(db, a.id)]
    pdf = build_pdf(assessment={"title": a.title, "topic": a.topic},
                    questions=[serialize.question(q) for q in serialize.questions_of(db, a.id)], sheets=sheets)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="MindTrace_{a.id}.pdf"'})


# ---------------------------------------------------------------- confirm / follow-up / results
@router.post("/assessments/{assessment_id}/confirm")
def confirm(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    a = own_assessment(db, teacher, assessment_id)
    scans = current_scans(db, a.id)
    pending = [s for s in scans if s.status == "needs_review"]
    if pending:
        raise api_error(409, "review_pending", f"{len(pending)} scan(s) still need review.")
    if not any(s.status == "accepted" for s in scans):
        raise api_error(409, "no_scans", "Scan at least one sheet first.")
    a.status = "confirmed"
    db.commit()
    return _assessment_out(db, a)


class FollowupBody(BaseModel):
    misconception_ids: list[str] = []
    num_questions: int = Field(0, ge=0, le=5)


@router.post("/assessments/{assessment_id}/followup")
def followup(assessment_id: str, body: FollowupBody | None = None, teacher: Teacher = Depends(current_teacher),
             db: Session = Depends(get_db)):
    body = body or FollowupBody()
    a = own_assessment(db, teacher, assessment_id)
    mids = body.misconception_ids
    if not mids:
        qs = [serialize.question(q) for q in serialize.questions_of(db, a.id)]
        scans = [serialize.scan(db, s) for s in current_scans(db, a.id)]
        report = insights.build({"id": a.id}, qs, scans, printed=len(sheets_of(db, a.id)), needs_review=0, with_ai=False)
        mids = [m["misconception_id"] for m in report["misconceptions"][:3]]
    if not mids:
        raise api_error(409, "nothing_to_follow_up", "No misconceptions found to follow up on.")
    n = body.num_questions or min(len(mids), 3)
    new_qs = ai_bridge.followup_questions(mids, n)
    f = Assessment(id=new_id("as"), class_id=a.class_id, title=f"{a.title}: follow-up", topic=a.topic,
                   concepts_text=a.concepts_text, status="draft", parent_assessment_id=a.id,
                   notes=["Follow-up for: " + ", ".join(mids)])
    db.add(f)
    db.flush()
    _store_questions(db, f, new_qs)
    db.commit()
    return _assessment_out(db, f)


@router.get("/assessments/{assessment_id}/results")
def results(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    """Teacher-only per-student view (names allowed here, never in the class report)."""
    a = own_assessment(db, teacher, assessment_id)
    qs = {q.id: q.data for q in serialize.questions_of(db, a.id)}
    by_sheet = {s.sheet_id: s for s in current_scans(db, a.id)}
    out = []
    for sh in sheets_of(db, a.id):
        stu = db.get(Student, sh.student_id)
        sc = by_sheet.get(sh.sheet_id)
        answers = sc.answers if sc else []
        correct = sum(1 for x in answers if qs.get(x["question_id"], {}).get("answer") == x.get("final"))
        out.append({"student": serialize.student(stu), "short_code": sh.short_code,
                    "scan_status": sc.status if sc else "missing", "correct": correct, "total": len(qs),
                    "answers": [{"question_id": x["question_id"], "final": x.get("final")} for x in answers]})
    return out
