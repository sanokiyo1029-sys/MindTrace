import re
from secrets import token_urlsafe
from typing import Literal

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config, gemini, serialize
from app.db import get_db
from app.errors import api_error
from app.ids import new_id
from app.models import AuthToken, Student, Teacher
from app.security import bearer, check_secret, current_session, hash_secret, issue_token
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


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


class TeacherSignup(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


@router.post("/teacher/signup")
def teacher_signup(body: TeacherSignup, db: Session = Depends(get_db)):
    """Create a teacher account with email + password. The new teacher starts with an empty workspace and
    creates their first class from the dashboard."""
    email, name = body.email.strip().lower(), " ".join(body.name.split())
    if not name:
        raise api_error(400, "bad_name", "Enter your name.")
    if not EMAIL_RE.match(email):
        raise api_error(400, "bad_email", "Enter a valid email address.")
    if len(body.password) < 8 or body.password.isdigit() or body.password.isalpha():
        raise api_error(400, "weak_password", "Use at least 8 characters, with letters and numbers.")
    if db.scalar(select(Teacher).where(Teacher.email == email)):
        raise api_error(409, "email_taken", "An account with this email already exists. Sign in instead.")
    t = Teacher(id=new_id("t"), email=email, name=name, password_hash=hash_secret(body.password))
    db.add(t)
    try:
        db.commit()
    except IntegrityError:  # same email at the same moment
        db.rollback()
        raise api_error(409, "email_taken", "An account with this email already exists. Sign in instead.") from None
    return {"token": issue_token(db, "teacher", t.id), "teacher": {"id": t.id, "name": t.name, "email": t.email}}


class GoogleLogin(BaseModel):
    credential: str  # the ID token Google Identity Services gives the browser (or a native Google sign-in later)
    allow_signup: bool = False
    role: Literal["teacher", "student"] = "teacher"
    student_link: StudentLogin | None = None


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


@router.post("/google/redirect", include_in_schema=False)
async def google_redirect(request: Request):
    """Google's redirect sign-in (no popup, so it works where popups are blocked) posts the ID token here. Check
    Google's double-submit CSRF cookie, then hand the token back to the page in the URL fragment (browsers never send
    fragments to servers). The page then signs in through POST /auth/google, which verifies the token as usual."""
    form = await request.form()
    credential, csrf = str(form.get("credential") or ""), str(form.get("g_csrf_token") or "")
    if not credential or not csrf or request.cookies.get("g_csrf_token") != csrf:
        return RedirectResponse("/login#google_error=csrf", status_code=303)
    return RedirectResponse(f"/login#google_credential={quote(credential, safe='')}", status_code=303)


@router.post("/google")
def google_login(body: GoogleLogin, db: Session = Depends(get_db)):
    """Sign in a verified Google identity for the requested role."""
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
    if "@" not in email or claims.get("email_verified") is not True:
        raise api_error(403, "google_email_unverified", "This Google account's email isn't verified.")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise api_error(401, "bad_google_token", "Google did not return a valid account identifier.")
    if body.role == "student":
        return _google_student(db, subject, body.student_link)
    by_subject = select(Teacher).where(Teacher.google_sub == subject)
    t = db.scalar(by_subject)
    if not t:
        matching_email = db.scalar(select(Teacher).where(Teacher.email == email))
        if matching_email and matching_email.google_sub:
            raise api_error(409, "google_account_conflict", "Choose the Google account you used to create this workspace.")
        # A verified third-party email may have changed owners since Google originally verified it.
        if email.endswith("@gmail.com") or claims.get("hd"):
            t = matching_email
            if not t and email in config.GOOGLE_TEACHER_EMAILS:
                t = db.scalar(select(Teacher).where(Teacher.email == TEACHER_EMAIL))
        if not t and not matching_email and body.allow_signup:
            try:
                with db.begin_nested():
                    t = Teacher(id=new_id("t"), email=email, name=str(claims.get("name") or email.split("@")[0])[:120],
                                google_sub=subject, password_hash=hash_secret(token_urlsafe(32)))
                    db.add(t)
                    db.flush()
            except IntegrityError:
                t = db.scalar(by_subject)
                if not t:
                    raise api_error(409, "google_account_conflict", "A teacher account already uses this email.") from None
    if not t:
        raise api_error(403, "google_not_linked", "This Google account isn't linked to a MindTrace teacher account. "
                                                  "Use your teacher email and password or ask your school to link it.")
    return {"token": issue_token(db, "teacher", t.id, google_subject=subject),
            "teacher": {"id": t.id, "name": t.name, "email": t.email}}


@router.post("/logout")
def logout(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    """Ends this session on the server too (teacher, Google or student token)."""
    row = db.get(AuthToken, creds.credentials) if creds else None
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


def _student_credentials(db: Session, body: StudentLogin) -> Student:
    s = db.scalar(select(Student).where(Student.student_code == body.student_code.strip().upper()))
    if not s or not check_secret(body.pin.strip(), s.pin_hash):
        raise api_error(401, "bad_login", "Wrong student code or PIN.")
    return s


def _google_student(db: Session, subject: str, credentials: StudentLogin | None):
    linked = db.scalar(select(Student).where(Student.google_sub == subject))
    if credentials is None:
        if linked is None:
            raise api_error(403, "google_student_link_required",
                            "Choose Create Student Account to connect Google using your student code and PIN.")
        student = linked
    else:
        student = _student_credentials(db, credentials)
        conflict = api_error(409, "google_student_link_conflict", "A different Google or student account is already linked.")
        if (linked and linked.id != student.id) or student.google_sub not in (None, subject):
            raise conflict
        if student.google_sub is None:
            try:
                changed = db.execute(update(Student).where(Student.id == student.id, Student.google_sub.is_(None))
                                     .values(google_sub=subject)).rowcount
            except IntegrityError:
                db.rollback()
                raise conflict from None
            if not changed:
                db.refresh(student)
                if student.google_sub != subject:
                    raise conflict
    return {"token": issue_token(db, "student", student.id), "student": serialize.student(student)}


@router.post("/student/login")
def student_login(body: StudentLogin, db: Session = Depends(get_db)):
    s = _student_credentials(db, body)
    return {"token": issue_token(db, "student", s.id), "student": serialize.student(s)}


@router.get("/me")
def me(session: AuthToken = Depends(current_session), db: Session = Depends(get_db)):
    """Who this token belongs to, so the app can restore a session after a refresh and route by role."""
    if session.role == "teacher":
        t = db.get(Teacher, session.subject_id)
        return {"role": "teacher", "teacher": {"id": t.id, "name": t.name, "email": t.email},
                # Gemini opens in the teacher's own Google account (no MindTrace key), so it needs a Google sign-in.
                "capabilities": {"gemini_account": t.email if session.google_subject else None}}
    return {"role": "student", "student": serialize.student(db.get(Student, session.subject_id))}
