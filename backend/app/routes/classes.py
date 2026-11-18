from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import marking, serialize
from app.db import get_db
from app.errors import api_error
from app.ids import join_code, new_id
from app.models import Assessment, ClassRoom, Student, Teacher
from app.security import current_teacher

router = APIRouter(prefix="/api/classes", tags=["classes"])


@router.get("")
def list_classes(teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    rows = db.scalars(select(ClassRoom).where(ClassRoom.teacher_id == teacher.id))
    return [_class_out(c) for c in rows]


def _class_out(c: ClassRoom) -> dict:
    return {"id": c.id, "name": c.name, "grade": c.grade, "join_code": c.join_code}


class NewClass(BaseModel):
    name: str = Field(min_length=1, max_length=40)   # e.g. "7B"
    grade: str = Field("", max_length=20)


@router.post("")
def create_class(body: NewClass, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    """A teacher (e.g. one who just signed up) adds a class to their own workspace."""
    name = " ".join(body.name.split())
    if not name:
        raise api_error(400, "bad_class_name", "Enter a class name, e.g. 7B.")
    if db.scalar(select(ClassRoom).where(ClassRoom.teacher_id == teacher.id, ClassRoom.name == name)):
        raise api_error(409, "class_exists", f"You already have a class called {name}.")
    c = ClassRoom(id=new_id("cl"), teacher_id=teacher.id, name=name, grade=body.grade.strip() or "7")
    db.add(c)
    db.commit()
    return _class_out(c)


@router.get("/{class_id}/students")
def list_students(class_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    _own_class(db, teacher, class_id)
    rows = db.scalars(select(Student).where(Student.class_id == class_id).order_by(Student.roll_no, Student.student_code))
    return [serialize.student(s) for s in rows]


@router.post("/{class_id}/join-code")
def new_join_code(class_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    """Replace the class code (e.g. if it was shared too widely). Students already in the class stay."""
    c = _own_class(db, teacher, class_id)
    c.join_code = join_code()
    db.commit()
    return _class_out(c)


class NewStudent(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    roll_no: str = Field(max_length=20)


@router.post("/{class_id}/students")
def add_student(class_id: str, body: NewStudent, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    """Teacher adds a student. The new login code and PIN are returned once, to hand to the student."""
    from app.routes.accounts import _clean_roll, enroll
    c = _own_class(db, teacher, class_id)
    name = " ".join(body.display_name.split())
    if not name:
        raise api_error(400, "bad_name", "Enter the student's name.")
    s, pin = enroll(db, c, name, _clean_roll(body.roll_no))
    db.commit()
    return {**serialize.student(s), "pin": pin}


def _class_student(db: Session, teacher: Teacher, class_id: str, student_id: str) -> Student:
    _own_class(db, teacher, class_id)
    s = db.get(Student, student_id)
    if not s or s.class_id != class_id:
        raise api_error(404, "not_found", "Student not found in this class.")
    return s


@router.delete("/{class_id}/students/{student_id}")
def remove_student(class_id: str, student_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    """Only students with no papers yet: results and scans are never deleted by removing someone from the list."""
    from app.models import AuthToken, ExamAttempt, Sheet
    s = _class_student(db, teacher, class_id, student_id)
    if db.scalar(select(Sheet).where(Sheet.student_id == s.id)):
        raise api_error(409, "has_papers", f"{s.display_name} already has papers in this class, so they can't be "
                                           "removed. Their results stay in your reports.")
    if db.scalar(select(ExamAttempt.id).where(ExamAttempt.student_id == s.id).limit(1)):
        raise api_error(409, "has_exam_attempt", "This student has an exam attempt. Keep their enrollment to preserve the report.")
    db.query(AuthToken).filter(AuthToken.subject_id == s.id).delete()
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.post("/{class_id}/students/{student_id}/reset")
def reset_student(class_id: str, student_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    """New PIN for the code + PIN login, and a temporary password if the student has their own account.
    Both are shown once; the student's other sessions end."""
    import secrets as _s
    from app.models import StudentAccount
    from app.security import end_sessions, hash_secret
    s = _class_student(db, teacher, class_id, student_id)
    pin = f"{_s.randbelow(10000):04d}"
    s.pin_hash = hash_secret(pin)
    end_sessions(db, s.id)
    out = {"student_code": s.student_code, "pin": pin, "temporary_password": None}
    acc = db.get(StudentAccount, s.account_id) if s.account_id else None
    if acc:
        temp = "mt-" + _s.token_urlsafe(6) + "7"
        acc.password_hash = hash_secret(temp)
        end_sessions(db, acc.id)
        out["temporary_password"] = temp
    db.commit()
    return out


def _own_class(db: Session, teacher: Teacher, class_id: str) -> ClassRoom:
    c = db.get(ClassRoom, class_id)
    if not c or c.teacher_id != teacher.id:  # 404, not 403: don't reveal other teachers' classes
        raise api_error(404, "not_found", "Class not found.")
    return c


@router.get("/{class_id}/overview")
def overview(class_id: str, subject: str = "mathematics", include_understanding: bool = False,
             teacher: Teacher = Depends(current_teacher),
             db: Session = Depends(get_db)):
    """Live counts for one class and subject, from its own records only."""
    from app import ai_bridge, class_understanding
    from app.models import Sheet
    from app.routes.assessments import score
    from app.routes.common import current_scans

    c = _own_class(db, teacher, class_id)
    subject = ai_bridge.subject_of(subject)
    rows = list(db.scalars(select(Assessment).where(Assessment.class_id == c.id).order_by(Assessment.created_at)))
    rows = [a for a in rows if (a.subject or "mathematics") == subject]
    students = list(db.scalars(select(Student).where(Student.class_id == c.id).order_by(Student.roll_no, Student.student_code)))
    if include_understanding:
        students_by_sheet = dict(db.execute(select(Sheet.sheet_id, Sheet.student_id)
                                            .join(Assessment, Sheet.assessment_id == Assessment.id)
                                            .join(Student, Sheet.student_id == Student.id)
                                            .where(Assessment.class_id == c.id, Student.class_id == c.id)).all())
        map_concepts, map_results = {}, []
        library = ai_bridge.misconception_library(subject)
    coverage: dict[str, dict] = {}
    history, needs_review = [], 0
    for a in rows:
        qs = {q.id: q.data for q in serialize.questions_of(db, a.id)}
        scans = current_scans(db, a.id)
        needs_review += sum(1 for s in scans if s.status == "needs_review")
        accepted = [s for s in scans if s.status == "accepted"]
        if include_understanding:
            class_understanding.add_assessment(map_concepts, map_results, a, qs, accepted, students_by_sheet, library)
        got = [score(qs, s.answers) for s in accepted]
        pct = round(100 * sum(g[0] for g in got) / sum(g[1] for g in got)) if got and sum(g[1] for g in got) else None
        concepts = {}
        for qid, q in qs.items():
            k = q.get("concept") or a.topic
            cov = coverage.setdefault(k, {"concept": k, "topic": a.topic, "questions": 0, "correct": 0, "answered": 0})
            cov["questions"] += 1
            if marking.written(q):
                continue
            for s in accepted:
                x = next((x for x in s.answers if x["question_id"] == qid), None)
                if x:
                    cov["answered"] += 1
                    cov["correct"] += x.get("final") == q.get("answer")
                    concepts.setdefault(k, [0, 0])
                    concepts[k][0] += x.get("final") == q.get("answer")
                    concepts[k][1] += 1
        history.append({"id": a.id, "title": a.title, "topic": a.topic, "status": a.status,
                        "created_at": a.created_at.isoformat(), "parent_assessment_id": a.parent_assessment_id,
                        "questions": len(qs), "verified": len(accepted), "score_pct": pct,
                        "concepts": {k: round(100 * v[0] / v[1]) for k, v in concepts.items() if v[1]}})
    result = {"class": {"id": c.id, "name": c.name, "grade": c.grade}, "subject": subject,
              "student_count": len(students), "assessment_count": len(rows),
              "topics": sorted({a.topic for a in rows}), "needs_review": needs_review,
              "concept_coverage": sorted(coverage.values(), key=lambda v: v["concept"]),
              "history": list(reversed(history))}
    if include_understanding:
        for concept in map_concepts.values():
            observed = (mistake for mistake in concept["mistakes"].values() if mistake["count"])
            concept["mistakes"] = sorted(observed, key=lambda mistake: -mistake["count"])[:3]
        result["understanding"] = {
            "students": [{"id": s.id, "display_name": s.display_name, "roll_no": s.roll_no} for s in students],
            "concepts": list(map_concepts.values()),
            "results": map_results,
        }
    return result


student_router = APIRouter(prefix="/api/students", tags=["classes"])


@student_router.get("/{student_id}/report")
def student_report(student_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    """Teacher-only: one student's papers across this teacher's assessments (answers, scan, feedback status)."""
    from app.models import Feedback, Scan, Sheet
    from app.routes.assessments import score

    s = db.get(Student, student_id)
    if not s:
        raise api_error(404, "not_found", "Student not found.")
    _own_class(db, teacher, s.class_id)
    out = []
    for sh in db.scalars(select(Sheet).where(Sheet.student_id == s.id)):
        a = db.get(Assessment, sh.assessment_id)
        sc = db.scalar(select(Scan).where(Scan.sheet_id == sh.sheet_id, Scan.is_current.is_(True)))
        qs = {q.id: q.data for q in serialize.questions_of(db, a.id)}
        answers = sc.answers if sc else []
        correct, total = score(qs, answers)
        fb = {f.question_id: f for f in db.scalars(select(Feedback).where(Feedback.scan_id == sc.id))} if sc else {}
        out.append({"assessment_id": a.id, "title": a.title, "topic": a.topic, "subject": a.subject or "mathematics",
                    "status": a.status, "created_at": a.created_at.isoformat(),
                    "scan_status": sc.status if sc else "missing", "image_url": sc.image_url if sc else None,
                    "correct": correct, "total": total,
                    "answers": [{"question_id": x["question_id"], "type": qs.get(x["question_id"], {}).get("type", "mcq"),
                                 "stem": qs.get(x["question_id"], {}).get("stem"), "final": x.get("final"),
                                 "correct_answer": qs.get(x["question_id"], {}).get("answer"), "text": x.get("text", ""),
                                 "feedback": {"text": fb[x["question_id"]].text, "status": fb[x["question_id"]].status}
                                 if x["question_id"] in fb else None} for x in answers]})
    out.sort(key=lambda r: r["created_at"], reverse=True)
    return {"student": serialize.student(s), "assessments": out}
