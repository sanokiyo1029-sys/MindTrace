import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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


def gemini_approved(session: AuthToken) -> bool:
    """Every signed-in teacher may use the assistant, unless the admin set GEMINI_APPROVED_GOOGLE_SUBS to limit it."""
    if session.role != "teacher":
        return False
    return not config.GEMINI_APPROVED_GOOGLE_SUBS or session.google_subject in config.GEMINI_APPROVED_GOOGLE_SUBS


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
