"""After scanning: teacher-verified feedback per answer, the teaching plan (edited recommendations, optional video
link) and follow-up practice the teacher assigns. Nothing here reaches a student until the teacher approves it."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import ai_bridge, gemini, serialize
from app.db import get_db
from app.errors import api_error
from app.ids import new_id
from app.models import Assignment, Feedback, PracticeSubmission, Student, Teacher
from app.routes.common import current_scans, own_assessment
from app.security import current_teacher

router = APIRouter(prefix="/api", tags=["teaching"])


def clean_video(url: str | None) -> str | None:
    url = (url or "").strip()
    if not url:
        return None
    if not url.startswith(("https://", "http://")) or len(url) > 500 or any(c in url for c in "\"'<> "):
        raise api_error(400, "bad_video_url", "Paste a full video link starting with https://.")
    return url


# ---------------------------------------------------------------- feedback
def _sync_feedback(db: Session, a) -> list[Feedback]:
    """One feedback row per answer worth a comment: every written answer, and every wrong bubble answer.
    Only confirmed (accepted) papers count. Wrong bubble answers get the library's student-friendly line as a
    suggestion; written answers wait for an AI suggestion or the teacher."""
    lib = ai_bridge.misconception_library()
    qs = {q.id: q.data for q in serialize.questions_of(db, a.id)}
    have = {(f.scan_id, f.question_id): f for f in db.scalars(select(Feedback).where(Feedback.assessment_id == a.id))}
    rows = []
    for sc in current_scans(db, a.id):
        if sc.status != "accepted" or not sc.sheet_id:
            continue
        student_id = serialize.scan(db, sc)["student"]["id"]
        for x in sc.answers or []:
            q = qs.get(x["question_id"])
            if not q:
                continue
            written = q.get("type") == "descriptive"
            if not (written and x.get("final") == "answered") and not (
                    not written and x.get("final") in ("A", "B", "C", "D") and x["final"] != q.get("answer")):
                continue
            f = have.get((sc.id, x["question_id"]))
            if f is None:
                suggestion, text = {"state": "not_requested"}, ""
                if not written:
                    mid = ((q.get("distractors") or {}).get(x["final"]) or {}).get("misconception_id")
                    m = lib.get(mid, {})
                    suggestion = {"state": "ok", "source": "library", "misconception_id": mid,
                                  "label": m.get("label", ""), "text": m.get("student_friendly", "")}
                    text = suggestion["text"]
                f = Feedback(id=new_id("fb"), assessment_id=a.id, scan_id=sc.id, student_id=student_id,
                             question_id=x["question_id"], suggestion=suggestion, concept=q.get("concept", ""), text=text)
                db.add(f)
            rows.append(f)
    db.commit()
    return rows


def _feedback_out(db: Session, f: Feedback, qs: dict, answers: dict) -> dict:
    q, x, stu = qs.get(f.question_id, {}), answers.get((f.scan_id, f.question_id), {}), db.get(Student, f.student_id)
    return {"id": f.id, "student": {"id": stu.id, "display_name": stu.display_name, "roll_no": stu.roll_no},
            "question_id": f.question_id, "question_type": q.get("type", "mcq"), "stem": q.get("stem", ""),
            "model_answer": q.get("model_answer"), "correct_answer": q.get("answer"),
            "response": {"final": x.get("final"), "text": x.get("text", ""), "text_state": x.get("text_state"),
                         "crop_url": x.get("reasoning_crop_url") or x.get("crop_url"),
                         "option_text": (q.get("options") or {}).get(x.get("final"))},
            "suggestion": f.suggestion or {"state": "not_requested"}, "concept": f.concept, "text": f.text,
            "video_url": f.video_url, "status": f.status, "version": f.version}


def _all_out(db: Session, a, rows: list[Feedback]) -> dict:
    qs = {q.id: q.data for q in serialize.questions_of(db, a.id)}
    answers = {(sc.id, x["question_id"]): x for sc in current_scans(db, a.id) for x in sc.answers or []}
    return {"items": [_feedback_out(db, f, qs, answers) for f in rows], "ai_available": gemini.enabled() or ai_bridge.ai_module_loaded()}


@router.get("/assessments/{assessment_id}/feedback")
def list_feedback(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    a = own_assessment(db, teacher, assessment_id)
    return _all_out(db, a, _sync_feedback(db, a))


@router.post("/assessments/{assessment_id}/feedback/suggest")
def suggest_feedback(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    """Ask the AI about every readable written answer that has no suggestion yet. Unclear handwriting is never sent:
    the teacher transcribes it first. A failure is recorded per answer; manual feedback stays possible."""
    a = own_assessment(db, teacher, assessment_id)
    rows = _sync_feedback(db, a)
    qs = {q.id: q.data for q in serialize.questions_of(db, a.id)}
    answers = {(sc.id, x["question_id"]): x for sc in current_scans(db, a.id) for x in sc.answers or []}
    for f in rows:
        q = qs[f.question_id]
        if q.get("type") != "descriptive" or f.status != "pending" or (f.suggestion or {}).get("state") == "ok":
            continue
        x = answers.get((f.scan_id, f.question_id), {})
        text = (x.get("text") or "").strip()
        if not text or x.get("text_state") in ("unclear", "missing", "not_read"):
            f.suggestion = {"state": "too_unclear", "message": "The answer isn't transcribed clearly yet. Correct the "
                            "transcription in Scan review, or write the feedback yourself."}
            continue
        try:
            f.suggestion = {"state": "ok", "source": "ai", **ai_bridge.response_suggestion(q, text, a.subject or "mathematics")}
            if not f.text:
                f.text = f.suggestion["text"]
        except gemini.GeminiError as exc:
            f.suggestion = {"state": "unavailable", "message": f"{exc.message} Write the feedback yourself."}
    db.commit()
    return _all_out(db, a, rows)


class FeedbackEdit(BaseModel):
    text: str | None = Field(None, max_length=1200)
    concept: str | None = Field(None, max_length=120)
    video_url: str | None = None
    status: str | None = Field(None, pattern="^(pending|approved|dismissed)$")
    base_version: int | None = None


@router.patch("/feedback/{feedback_id}")
def edit_feedback(feedback_id: str, body: FeedbackEdit, teacher: Teacher = Depends(current_teacher),
                  db: Session = Depends(get_db)):
    f = db.get(Feedback, feedback_id)
    if not f:
        raise api_error(404, "not_found", "Feedback not found.")
    a = own_assessment(db, teacher, f.assessment_id)
    if body.base_version is not None and body.base_version != f.version:
        raise api_error(409, "conflict", "This feedback was changed somewhere else. Check the newer version first.",
                        current=_all_out(db, a, [f])["items"][0])
    if body.text is not None:
        f.text = body.text.strip()
    if body.concept is not None:
        f.concept = body.concept.strip()
    if body.video_url is not None:
        f.video_url = clean_video(body.video_url)
    if body.status:
        if body.status == "approved" and not f.text.strip():
            raise api_error(400, "empty_feedback", "Write the feedback before approving it.")
        f.status = body.status
    f.version += 1
    db.commit()
    return _all_out(db, a, [f])["items"][0]


# ---------------------------------------------------------------- teaching plan
class PlanEdit(BaseModel):
    title: str = Field("", max_length=120)
    minutes: int = Field(5, ge=1, le=60)
    steps: list[str] = Field(default_factory=list, max_length=8)
    video_url: str | None = None
    status: str = Field("planned", pattern="^(planned|dismissed)$")
    note: str = Field("", max_length=500)


@router.put("/assessments/{assessment_id}/plan/{misconception_id}")
def edit_plan(assessment_id: str, misconception_id: str, body: PlanEdit, teacher: Teacher = Depends(current_teacher),
              db: Session = Depends(get_db)):
    """The teacher's version of a teaching recommendation (edited activity, optional video, or dismissed)."""
    a = own_assessment(db, teacher, assessment_id)
    plan = dict(a.plan or {})
    plan[misconception_id] = {**body.model_dump(), "video_url": clean_video(body.video_url),
                              "steps": [s.strip() for s in body.steps if s.strip()]}
    a.plan = plan
    db.commit()
    return plan


# ---------------------------------------------------------------- assigned practice
@router.post("/assessments/{assessment_id}/assign")
def assign(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    """Make an approved (usually follow-up) assessment available to the class as online practice."""
    a = own_assessment(db, teacher, assessment_id)
    if a.status == "draft":
        raise api_error(409, "not_approved", "Approve the questions before assigning them.")
    existing = db.scalar(select(Assignment).where(Assignment.assessment_id == a.id))
    if not existing:
        db.add(Assignment(id=new_id("asg"), assessment_id=a.id, class_id=a.class_id))
        try:
            db.commit()
        except IntegrityError:  # assigned twice at the same moment: once is enough
            db.rollback()
    return practice_status(assessment_id, teacher, db)


@router.get("/assessments/{assessment_id}/practice")
def practice_status(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    a = own_assessment(db, teacher, assessment_id)
    asg = db.scalar(select(Assignment).where(Assignment.assessment_id == a.id))
    if not asg:
        return {"assigned": False, "students": []}
    subs = {p.student_id: p for p in db.scalars(select(PracticeSubmission).where(PracticeSubmission.assignment_id == asg.id))}
    students = db.scalars(select(Student).where(Student.class_id == a.class_id).order_by(Student.roll_no))
    return {"assigned": True, "assignment_id": asg.id, "students": [
        {"student": serialize.student(s), "status": "submitted" if s.id in subs else "not_started",
         "submitted_at": subs[s.id].created_at.isoformat() if s.id in subs else None} for s in students]}
