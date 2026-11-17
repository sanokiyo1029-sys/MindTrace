import hashlib
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import insights, serialize
from app.db import get_db
from app.errors import api_error
from app.models import Teacher
from app.routes.common import current_scans, own_assessment, sheets_of
from app.security import current_teacher

router = APIRouter(prefix="/api", tags=["insights"])
_cache: dict[str, tuple[str, dict]] = {}


@router.get("/assessments/{assessment_id}/insights")
def get_insights(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    a = own_assessment(db, teacher, assessment_id)
    scans = [serialize.scan(db, s) for s in current_scans(db, a.id)]
    pending = sum(1 for s in scans if s["status"] == "needs_review")
    if pending:
        raise api_error(409, "review_pending", f"Review {pending} flagged scan(s) first. Insights use only confirmed answers.")
    if not any(s["status"] == "accepted" for s in scans):
        raise api_error(409, "no_scans", "Scan at least one sheet first.")
    qs = [serialize.question(q) for q in serialize.questions_of(db, a.id)]
    printed = len(sheets_of(db, a.id))
    key = hashlib.sha1(json.dumps([qs, [(s["sheet_id"], [x.get("final") for x in s["answers"]]) for s in scans], printed],
                                  sort_keys=True, default=str).encode()).hexdigest()
    hit = _cache.get(a.id)
    if hit and hit[0] == key:
        return hit[1]
    report = insights.build({"id": a.id}, qs, scans, printed=printed, needs_review=pending)
    _cache[a.id] = (key, report)
    return report
