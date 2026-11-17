from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import api_error
from app.models import Assessment, ClassRoom, Scan, Sheet, Teacher


def own_assessment(db: Session, teacher: Teacher, assessment_id: str) -> Assessment:
    a = db.get(Assessment, assessment_id)
    if not a:
        raise api_error(404, "not_found", "Assessment not found.")
    cls = db.get(ClassRoom, a.class_id)
    if not cls or cls.teacher_id != teacher.id:
        raise api_error(403, "forbidden", "This assessment belongs to another teacher.")
    return a


def sheets_of(db: Session, assessment_id: str) -> list[Sheet]:
    return list(db.scalars(select(Sheet).where(Sheet.assessment_id == assessment_id).order_by(Sheet.short_code)))


def current_scans(db: Session, assessment_id: str) -> list[Scan]:
    return list(db.scalars(select(Scan).where(Scan.assessment_id == assessment_id, Scan.is_current.is_(True))
                           .order_by(Scan.created_at)))
