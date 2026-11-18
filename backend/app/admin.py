"""Admin commands, run on the server (e.g. Render Shell):

    python -m app.admin reset-link <email>    one-time password-reset link (when email sending isn't set up)

The link is printed only to this terminal, never logged by the web app."""
import sys

from sqlalchemy import select

from app import config
from app.db import SessionLocal, init_db
from app.models import StudentAccount, Teacher
from app.routes.accounts import RESET_MINUTES, make_reset


def reset_link(email: str) -> str:
    init_db()
    with SessionLocal() as db:
        email = email.strip().lower()
        t = db.scalar(select(Teacher).where(Teacher.email == email))
        acc = None if t else db.scalar(select(StudentAccount).where(StudentAccount.email == email))
        if not (t or acc):
            raise SystemExit(f"No account uses {email}.")
        token = make_reset(db, "teacher" if t else "student_account", (t or acc).id)
    return f"{config.PUBLIC_URL or 'http://localhost:8000'}/reset-password#token={token}"


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "reset-link":
        print(f"Valid for {RESET_MINUTES} minutes, one use:\n{reset_link(sys.argv[2])}")
    else:
        print(__doc__)
