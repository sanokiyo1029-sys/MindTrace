from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import serialize
from app.db import get_db
from app.errors import api_error
from app.models import Assessment, ClassRoom, Student, Teacher
from app.security import current_teacher

router = APIRouter(prefix="/api/classes", tags=["classes"])


@router.get("")
def list_classes(teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    rows = db.scalars(select(ClassRoom).where(ClassRoom.teacher_id == teacher.id))
    return [{"id": c.id, "name": c.name, "grade": c.grade} for c in rows]


@router.get("/{class_id}/students")
def list_students(class_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    _own_class(db, teacher, class_id)
    rows = db.scalars(select(Student).where(Student.class_id == class_id).order_by(Student.roll_no, Student.student_code))
    return [serialize.student(s) for s in rows]


def _own_class(db: Session, teacher: Teacher, class_id: str) -> ClassRoom:
    c = db.get(ClassRoom, class_id)
    if not c or c.teacher_id != teacher.id:  # 404, not 403: don't reveal other teachers' classes
        raise api_error(404, "not_found", "Class not found.")
    return c


@router.get("/{class_id}/overview")
def overview(class_id: str, subject: str = "mathematics", teacher: Teacher = Depends(current_teacher),
             db: Session = Depends(get_db)):
    """Live counts for one class and subject, from its own records only."""
    from app import ai_bridge
    from app.routes.assessments import score
    from app.routes.common import current_scans

    c = _own_class(db, teacher, class_id)
    subject = ai_bridge.subject_of(subject)
    rows = list(db.scalars(select(Assessment).where(Assessment.class_id == c.id).order_by(Assessment.created_at)))
    rows = [a for a in rows if (a.subject or "mathematics") == subject]
    coverage: dict[str, dict] = {}
    history, needs_review = [], 0
    for a in rows:
        qs = {q.id: q.data for q in serialize.questions_of(db, a.id)}
        scans = current_scans(db, a.id)
        needs_review += sum(1 for s in scans if s.status == "needs_review")
        accepted = [s for s in scans if s.status == "accepted"]
        got = [score(qs, s.answers) for s in accepted]
        pct = round(100 * sum(g[0] for g in got) / sum(g[1] for g in got)) if got and sum(g[1] for g in got) else None
        concepts = {}
        for qid, q in qs.items():
            k = q.get("concept") or a.topic
            cov = coverage.setdefault(k, {"concept": k, "topic": a.topic, "questions": 0, "correct": 0, "answered": 0})
            cov["questions"] += 1
            if q.get("type", "mcq") == "descriptive":
                continue
            for s in accepted:
                x = next((x for x in s.answers if x["question_id"] == qid), None)
                if x:
                    cov["answered"] += 1
                    cov["correct"] += x.get("final") == q.get("answer")
                    concepts.setdefault(k, [0, 0])
                    concepts[k][0] += x.get("final") == q.get("answer")
                    concepts[k][1] += 1
        history.append({"id": a.id, "title": a.title, "topic": a.topic, "status": a.status,
                        "created_at": a.created_at.isoformat(), "parent_assessment_id": a.parent_assessment_id,
                        "questions": len(qs), "verified": len(accepted), "score_pct": pct,
                        "concepts": {k: round(100 * v[0] / v[1]) for k, v in concepts.items() if v[1]}})
    students = db.scalars(select(Student).where(Student.class_id == c.id))
    return {"class": {"id": c.id, "name": c.name, "grade": c.grade}, "subject": subject,
            "student_count": len(list(students)), "assessment_count": len(rows),
            "topics": sorted({a.topic for a in rows}), "needs_review": needs_review,
            "concept_coverage": sorted(coverage.values(), key=lambda v: v["concept"]),
            "history": list(reversed(history))}


student_router = APIRouter(prefix="/api/students", tags=["classes"])


@student_router.get("/{student_id}/report")
def student_report(student_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    """Teacher-only: one student's papers across this teacher's assessments (answers, scan, feedback status)."""
    from app.models import Feedback, Scan, Sheet
    from app.routes.assessments import score

    s = db.get(Student, student_id)
    if not s:
        raise api_error(404, "not_found", "Student not found.")
    _own_class(db, teacher, s.class_id)
    out = []
    for sh in db.scalars(select(Sheet).where(Sheet.student_id == s.id)):
        a = db.get(Assessment, sh.assessment_id)
        sc = db.scalar(select(Scan).where(Scan.sheet_id == sh.sheet_id, Scan.is_current.is_(True)))
        qs = {q.id: q.data for q in serialize.questions_of(db, a.id)}
        answers = sc.answers if sc else []
        correct, total = score(qs, answers)
        fb = {f.question_id: f for f in db.scalars(select(Feedback).where(Feedback.scan_id == sc.id))} if sc else {}
        out.append({"assessment_id": a.id, "title": a.title, "topic": a.topic, "subject": a.subject or "mathematics",
                    "status": a.status, "created_at": a.created_at.isoformat(),
                    "scan_status": sc.status if sc else "missing", "image_url": sc.image_url if sc else None,
                    "correct": correct, "total": total,
                    "answers": [{"question_id": x["question_id"], "type": qs.get(x["question_id"], {}).get("type", "mcq"),
                                 "stem": qs.get(x["question_id"], {}).get("stem"), "final": x.get("final"),
                                 "correct_answer": qs.get(x["question_id"], {}).get("answer"), "text": x.get("text", ""),
                                 "feedback": {"text": fb[x["question_id"]].text, "status": fb[x["question_id"]].status}
                                 if x["question_id"] in fb else None} for x in answers]})
    out.sort(key=lambda r: r["created_at"], reverse=True)
    return {"student": serialize.student(s), "assessments": out}
