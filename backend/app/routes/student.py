from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ai_bridge, serialize
from app.db import get_db
from app.models import Assessment, Scan, Sheet, Student
from app.security import current_student

router = APIRouter(prefix="/api/student", tags=["student"])


@router.get("/me/results")
def my_results(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    """Only ever this student's own answers."""
    lib = ai_bridge.misconception_library()
    out = []
    for sh in db.scalars(select(Sheet).where(Sheet.student_id == student.id)):
        sc = db.scalar(select(Scan).where(Scan.sheet_id == sh.sheet_id, Scan.is_current.is_(True), Scan.status == "accepted"))
        if not sc:
            continue
        a = db.get(Assessment, sh.assessment_id)
        qs = {q.id: q.data for q in serialize.questions_of(db, a.id)}
        answers = []
        for x in sc.answers:
            q = qs.get(x["question_id"])
            if not q:
                continue
            chosen = x.get("final")
            maybe = None
            if chosen in ("A", "B", "C", "D") and chosen != q["answer"]:
                mid = ((q.get("distractors") or {}).get(chosen) or {}).get("misconception_id")
                maybe = lib.get(mid, {}).get("student_friendly")
            answers.append({"question_id": x["question_id"], "stem": q["stem"], "options": q["options"],
                            "chosen": chosen, "correct": q["answer"], "explanation": q.get("explanation"), "maybe": maybe})
        out.append({"assessment_id": a.id, "title": a.title, "answers": answers})
    return {"student": {"display_name": student.display_name}, "assessments": out}
