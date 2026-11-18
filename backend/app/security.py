import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.db import get_db
from app.models import AuthToken, Student, Teacher


def hash_secret(secret: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def check_secret(secret: str, stored: str) -> bool:
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_secret(secret, salt), stored)


def issue_token(db: Session, role: str, subject_id: str, *, google_subject: str | None = None) -> str:
    tok = secrets.token_urlsafe(24)
    db.add(AuthToken(token=tok, role=role, subject_id=subject_id, google_subject=google_subject))
    db.commit()
    return tok


# HTTPBearer (not a raw Header) so /docs shows an Authorize button; same "Authorization: Bearer" header
bearer = HTTPBearer(auto_error=False)


def _token_from(creds: HTTPAuthorizationCredentials | None, token_q: str | None) -> str | None:
    if creds:
        return creds.credentials
    return token_q  # ?token= lets <a href> / <img> open the PDF and scan images


def token_row(db: Session, tok: str | None) -> AuthToken:
    """The live session for a token (any role), or 401. Expired sessions are removed."""
    if not tok:
        raise HTTPException(401, detail={"error": "unauthorized", "message": "Please log in."})
    row = db.get(AuthToken, tok)
    if not row:
        raise HTTPException(401, detail={"error": "unauthorized", "message": "Please log in again."})
    made = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - made > timedelta(hours=config.SESSION_HOURS):
        db.delete(row)
        db.commit()
        raise HTTPException(401, detail={"error": "session_expired", "message": "Your session expired. Please sign in again."})
    return row


def _lookup(db: Session, tok: str | None, role: str):
    row = token_row(db, tok)
    if row.role != role:
        raise HTTPException(401, detail={"error": "unauthorized", "message": "Please log in again."})
    return row.subject_id


def current_session(creds: HTTPAuthorizationCredentials | None = Depends(bearer), token: str | None = Query(default=None),
                    db: Session = Depends(get_db)) -> AuthToken:
    return token_row(db, _token_from(creds, token))


def current_teacher(creds: HTTPAuthorizationCredentials | None = Depends(bearer), token: str | None = Query(default=None),
                    db: Session = Depends(get_db)) -> Teacher:
    return db.get(Teacher, _lookup(db, _token_from(creds, token), "teacher"))


def current_student(creds: HTTPAuthorizationCredentials | None = Depends(bearer), token: str | None = Query(default=None),
                    db: Session = Depends(get_db)) -> Student:
    return db.get(Student, _lookup(db, _token_from(creds, token), "student"))


def current_enrollments(session: AuthToken = Depends(current_session), db: Session = Depends(get_db)) -> list[Student]:
    """The signed-in student's class enrollments. A student ACCOUNT (email + password) may be in several classes;
    an old-style code + PIN session is exactly one enrollment."""
    from app.models import StudentAccount
    if session.role != "student":
        raise HTTPException(401, detail={"error": "unauthorized", "message": "Please log in as a student."})
    if db.get(StudentAccount, session.subject_id):
        return list(db.scalars(select(Student).where(Student.account_id == session.subject_id)))
    s = db.get(Student, session.subject_id)
    if not s:
        raise HTTPException(401, detail={"error": "unauthorized", "message": "Please log in again."})
    return [s]


def end_sessions(db: Session, subject_id: str):
    """Sign a person out everywhere (after a password change or reset)."""
    db.query(AuthToken).filter(AuthToken.subject_id == subject_id).delete()


# ponytail: in-memory, per process. Fine for one Render instance; move to the database if it ever runs on several.
_FAILS: dict[str, list[float]] = {}
MAX_FAILS, WINDOW = 5, 600.0


def check_throttle(key: str):
    import time
    now = time.monotonic()
    recent = [t for t in _FAILS.get(key, []) if now - t < WINDOW]
    _FAILS[key] = recent
    if len(recent) >= MAX_FAILS:
        raise HTTPException(429, detail={"error": "too_many_attempts",
                                         "message": "Too many wrong attempts. Wait 10 minutes and try again."})


def record_failure(key: str):
    import time
    _FAILS.setdefault(key, []).append(time.monotonic())


def clear_failures(key: str):
    _FAILS.pop(key, None)
