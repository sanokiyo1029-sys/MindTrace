"""DB rows -> the exact JSON shapes in docs/CONTRACTS.md."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assessment, Question, Scan, Sheet, Student


def question(q: Question) -> dict:
    return {**q.data, "id": q.id, "assessment_id": q.assessment_id, "status": q.status}


def questions_of(db: Session, assessment_id: str) -> list[Question]:
    return list(db.scalars(select(Question).where(Question.assessment_id == assessment_id).order_by(Question.position)))


def assessment(db: Session, a: Assessment) -> dict:
    return {
        "id": a.id, "class_id": a.class_id, "title": a.title, "topic": a.topic,
        "concepts_text": a.concepts_text, "status": a.status,
        "parent_assessment_id": a.parent_assessment_id, "notes": a.notes or [],
        "questions": [question(q) for q in questions_of(db, a.id)],
    }


def student(s: Student) -> dict:
    return {"id": s.id, "class_id": s.class_id, "display_name": s.display_name, "student_code": s.student_code,
            "roll_no": s.roll_no}


def scan(db: Session, sc: Scan) -> dict:
    sheet = db.get(Sheet, sc.sheet_id) if sc.sheet_id else None
    stu = db.get(Student, sheet.student_id) if sheet else None
    identity = sc.identity or {}
    return {
        "scan_id": sc.id, "status": sc.status, "reject_reason": sc.reject_reason,
        "sheet_id": sc.sheet_id, "short_code": sheet.short_code if sheet else None,
        "student": {"id": stu.id, "display_name": stu.display_name, "roll_no": stu.roll_no} if stu else None,
        "roll_number": {"read": sc.roll_number, "status": identity.get("status", "matched" if stu else "unknown"),
                        "candidates": identity.get("candidates", [])},
        "extracted_by": sc.extracted_by,
        "warnings": sc.warnings or [],
        "answers": sc.answers or [], "image_url": sc.image_url, "duplicate_of": sc.duplicate_of,
    }
