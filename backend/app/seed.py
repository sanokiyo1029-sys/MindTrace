"""Demo data: 1 teacher, class 7A, 5 FICTIONAL students.
Run: python -m app.seed          (adds what's missing)
     python -m app.seed --reset  (wipes the database and media first)
"""
import json
import shutil
import sys

from sqlalchemy import select

from app import demo_data
from app.config import FIXTURES_DIR, MEDIA_DIR
from app.db import Base, SessionLocal, engine, init_db
from app.models import ClassRoom, Student, Teacher
from app.security import hash_secret

TEACHER_EMAIL = "teacher@mindtrace.demo"
TEACHER_PASSWORD = "demo1234"


def roster() -> list[dict]:
    path = FIXTURES_DIR / "roster.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data and all({"display_name", "student_code", "pin"} <= set(s) for s in data):
                return data
        except Exception:
            pass
    return demo_data.ROSTER


def seed(reset: bool = False) -> dict:
    if reset:
        Base.metadata.drop_all(engine)
        shutil.rmtree(MEDIA_DIR / "scans", ignore_errors=True)
        (MEDIA_DIR / "scans").mkdir(parents=True, exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        t = db.scalar(select(Teacher).where(Teacher.email == TEACHER_EMAIL))
        if not t:
            t = Teacher(id="t_demo", email=TEACHER_EMAIL, name="Demo Teacher", password_hash=hash_secret(TEACHER_PASSWORD))
            db.add(t)
        if not db.get(ClassRoom, "cl_7a"):
            db.add(ClassRoom(id="cl_7a", teacher_id=t.id, name="7A", grade="7"))
        db.flush()
        for i, s in enumerate(roster(), 1):
            code = s["student_code"].upper()
            if not db.scalar(select(Student).where(Student.student_code == code)):
                db.add(Student(id=s.get("id") or f"st_{i:02d}", class_id="cl_7a", display_name=s["display_name"],
                               student_code=code, pin_hash=hash_secret(str(s["pin"]))))
        db.commit()
        return {"teacher": TEACHER_EMAIL, "password": TEACHER_PASSWORD,
                "students": [(s["student_code"], str(s["pin"])) for s in roster()]}
    finally:
        db.close()


if __name__ == "__main__":
    info = seed(reset="--reset" in sys.argv)
    print(f"Teacher login: {info['teacher']} / {info['password']}")
    print("Student logins (code / PIN):", ", ".join(f"{c} / {p}" for c, p in info["students"]))
