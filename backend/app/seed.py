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
from app.rolls import from_student_code
from app.security import hash_secret

TEACHER_EMAIL = "teacher@mindtrace.demo"
TEACHER_PASSWORD = "demo1234"

# A separate teacher + fictional class for testing the Android app, so test scans never touch demo class 7A.
APK_TESTER_EMAIL = "apk.tester@mindtrace.demo"
APK_TESTER_PASSWORD = "apk-b3t1uq48"
APK_TEST_ROSTER = [  # (name, student code, roll no, PIN), all fictional
    ("Ishaan", "7T-01", "01", "1212"), ("Tara", "7T-02", "02", "2323"), ("Neel", "7T-03", "03", "3434"),
    ("Zara", "7T-04", "04", "4545"), ("Advik", "7T-05", "05", "5656"),
]


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
            db.flush()  # write the teacher before inserting the class that references it
        if not db.get(ClassRoom, "cl_7a"):
            db.add(ClassRoom(id="cl_7a", teacher_id=t.id, name="7A", grade="7"))
        db.flush()
        for i, s in enumerate(roster(), 1):
            code = s["student_code"].upper()
            if not db.scalar(select(Student).where(Student.student_code == code)):
                db.add(Student(id=s.get("id") or f"st_{i:02d}", class_id="cl_7a", display_name=s["display_name"],
                               student_code=code, roll_no=str(s.get("roll_no") or from_student_code(code)),
                               pin_hash=hash_secret(str(s["pin"]))))
        tt = db.scalar(select(Teacher).where(Teacher.email == APK_TESTER_EMAIL))
        if not tt:
            tt = Teacher(id="t_apk_tester", email=APK_TESTER_EMAIL, name="APK Tester",
                         password_hash=hash_secret(APK_TESTER_PASSWORD))
            db.add(tt)
            db.flush()
        if not db.get(ClassRoom, "cl_7t"):
            db.add(ClassRoom(id="cl_7t", teacher_id=tt.id, name="7T", grade="7"))
        db.flush()
        for name, code, roll, pin in APK_TEST_ROSTER:
            if not db.scalar(select(Student).where(Student.student_code == code)):
                db.add(Student(id=f"st_{code.lower().replace('-', '_')}", class_id="cl_7t", display_name=name,
                               student_code=code, roll_no=roll, pin_hash=hash_secret(pin)))
        db.commit()
        return {"teacher": TEACHER_EMAIL, "password": TEACHER_PASSWORD,
                "students": [(s["student_code"], str(s["pin"])) for s in roster()]}
    finally:
        db.close()


if __name__ == "__main__":
    info = seed(reset="--reset" in sys.argv)
    print(f"Teacher login: {info['teacher']} / {info['password']}")
    print("Student logins (code / PIN):", ", ".join(f"{c} / {p}" for c, p in info["students"]))
