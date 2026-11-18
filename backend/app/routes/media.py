"""Scan photos and crops, served only to the teacher who owns the assessment, or to the student whose paper it is
once their results are released. Same URLs as before (/api/media/scans/...); add ?token= for <img> tags."""
import re

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import media_store
from app.config import MEDIA_DIR
from app.db import get_db
from app.errors import api_error
from app.models import Assessment, AuthToken, ClassRoom, Question, Scan, Sheet, Student
from app.routes.student import released
from app.security import current_enrollments, current_session

router = APIRouter(prefix="/api/media", tags=["media"])
NAME = re.compile(r"^(sc_[a-z0-9]+)(_q\d+(_why)?)?\.jpg$")
QUESTION_PICTURE = re.compile(r"^(q_[a-z0-9]+)_\d+\.jpg$")


@router.get("/questions/{name}", include_in_schema=False)
def question_picture(name: str, session: AuthToken = Depends(current_session), db: Session = Depends(get_db)):
    """A question's picture: the teacher who owns it, or a student in that class."""
    m = QUESTION_PICTURE.match(name)
    q = db.get(Question, m.group(1)) if m else None
    path = MEDIA_DIR / "questions" / name
    if not q or not media_store.ensure(path) or not (q.data.get("image_url") or "").endswith("/" + name):
        raise api_error(404, "not_found", "Image not found.")
    class_id = db.get(Assessment, q.assessment_id).class_id
    if session.role == "teacher":
        allowed = db.get(ClassRoom, class_id).teacher_id == session.subject_id
    else:
        allowed = any(s.class_id == class_id for s in current_enrollments(session, db))
    if not allowed:
        raise api_error(403, "forbidden", "You can't open this image.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/scans/{name}", include_in_schema=False)
def scan_image(name: str, session: AuthToken = Depends(current_session), db: Session = Depends(get_db)):
    m = NAME.match(name)
    sc = db.get(Scan, m.group(1)) if m else None
    path = MEDIA_DIR / "scans" / name
    if not sc or not media_store.ensure(path):
        raise api_error(404, "not_found", "Image not found.")
    a = db.get(Assessment, sc.assessment_id)
    if session.role == "teacher":
        allowed = db.get(ClassRoom, a.class_id).teacher_id == session.subject_id
    else:
        sheet = db.get(Sheet, sc.sheet_id) if sc.sheet_id else None
        mine = {session.subject_id} | {s.id for s in db.scalars(select(Student).where(Student.account_id == session.subject_id))}
        allowed = bool(sheet) and sheet.student_id in mine and sc.is_current and released(a, sc)
    if not allowed:
        raise api_error(403, "forbidden", "You can't open this image.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
