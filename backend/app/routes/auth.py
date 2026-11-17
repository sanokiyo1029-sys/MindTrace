from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config, serialize
from app.db import get_db
from app.errors import api_error
from app.models import AuthToken, Student, Teacher
from app.security import bearer, check_secret, issue_token
from app.seed import TEACHER_EMAIL

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TeacherLogin(BaseModel):
    email: str
    password: str


class StudentLogin(BaseModel):
    student_code: str
    pin: str


@router.post("/teacher/login")
def teacher_login(body: TeacherLogin, db: Session = Depends(get_db)):
    t = db.scalar(select(Teacher).where(Teacher.email == body.email.strip().lower()))
    if not t or not check_secret(body.password, t.password_hash):
        raise api_error(401, "bad_login", "Wrong email or password.")
    return {"token": issue_token(db, "teacher", t.id), "teacher": {"id": t.id, "name": t.name, "email": t.email}}


class GoogleLogin(BaseModel):
    credential: str  # the ID token Google Identity Services gives the browser (or a native Google sign-in later)


@router.get("/config")
def auth_config():
    """What the sign-in screen can offer. An OAuth client ID is public by design; no secret is involved."""
    return {"google_client_id": config.GOOGLE_CLIENT_IDS[0] if config.GOOGLE_CLIENT_IDS else None}


def _verify_google(credential: str) -> dict:  # tests replace this
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token
    # checks Google's signature, issuer, expiry and that the token was made for one of OUR client IDs
    return id_token.verify_oauth2_token(credential, google_requests.Request(), audience=config.GOOGLE_CLIENT_IDS,
                                        clock_skew_in_seconds=10)


@router.post("/google")
def google_login(body: GoogleLogin, db: Session = Depends(get_db)):
    """'Continue with Google' is for TEACHERS only, and only for linked accounts: the verified Google email must
    equal a teacher's email, or be listed in GOOGLE_TEACHER_EMAILS (those sign in as the demo teacher).
    It never creates accounts or grants student access; students keep student code + PIN."""
    if not config.GOOGLE_CLIENT_IDS:
        raise api_error(503, "google_not_configured", "Google sign-in isn't set up on this server.")
    try:
        from google.auth.exceptions import GoogleAuthError, TransportError
    except ImportError:
        raise api_error(503, "google_not_configured", "Google sign-in needs the google-auth package on the server.")
    try:
        claims = _verify_google(body.credential)
    except TransportError:
        raise api_error(503, "google_unreachable", "Couldn't reach Google to check the sign-in. Try again.")
    except (ValueError, GoogleAuthError):
        raise api_error(401, "bad_google_token", "Google sign-in didn't complete. Please try again.")
    email = str(claims.get("email", "")).strip().lower()
    if not email or claims.get("email_verified") is not True:
        raise api_error(403, "google_email_unverified", "This Google account's email isn't verified.")
    t = db.scalar(select(Teacher).where(Teacher.email == email))
    if not t and email in config.GOOGLE_TEACHER_EMAILS:
        t = db.scalar(select(Teacher).where(Teacher.email == TEACHER_EMAIL))
    if not t:
        raise api_error(403, "google_not_linked", f"{email} isn't linked to a MindTrace teacher account. "
                                                  "Sign in with email and password, or ask the admin to link it.")
    return {"token": issue_token(db, "teacher", t.id), "teacher": {"id": t.id, "name": t.name, "email": t.email}}


@router.post("/logout")
def logout(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    """Ends this session on the server too (teacher, Google or student token)."""
    row = db.get(AuthToken, creds.credentials) if creds else None
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.post("/student/login")
def student_login(body: StudentLogin, db: Session = Depends(get_db)):
    s = db.scalar(select(Student).where(Student.student_code == body.student_code.strip().upper()))
    if not s or not check_secret(body.pin.strip(), s.pin_hash):
        raise api_error(401, "bad_login", "Wrong student code or PIN.")
    return {"token": issue_token(db, "student", s.id), "student": serialize.student(s)}
