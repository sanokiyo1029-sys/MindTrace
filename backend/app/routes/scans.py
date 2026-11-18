"""Scanning completed papers: photo -> Gemini reads roll number + marks -> roster match -> teacher review -> confirm.

Every scan starts in needs_review: the teacher checks the student and the answers before anything counts.
Scores and insights are computed later from the confirmed answers and the approved answer key (deterministic).
"""
import threading

import cv2
from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config, gemini, rolls, serialize
from app.config import MEDIA_DIR
from app.db import get_db
from app.errors import api_error
from app.ids import new_id
from app.layout import paper_code, question_types
from app.models import Assessment, ClassRoom, Scan, Sheet, Student, Teacher
from app.routes.common import current_scans, own_assessment, sheets_of
from app.scanner import gemini_reader, omr, pipeline
from app.security import current_teacher

router = APIRouter(prefix="/api", tags=["scans"])
SCAN_DIR = MEDIA_DIR / "scans"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
_attach_lock = threading.Lock()  # one decision at a time about which scan is a student's live one

IDENTITY_WARNINGS = {
    "unreadable": "Roll number could not be read. Enter it manually or retake the photo.",
    "unknown": "Roll number {roll} isn't on the {cls} roster. Check it, or choose the student.",
    "ambiguous": "Roll number {roll} could be more than one student. Choose the right one.",
}


def _save(img, name: str, max_side: int = 1600) -> str:
    h, w = img.shape[:2]
    if max(h, w) > max_side:
        s = max_side / max(h, w)
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(SCAN_DIR / name), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return f"/api/media/scans/{name}"


def _jpeg(img, max_side: int = 2000) -> bytes:
    h, w = img.shape[:2]
    if max(h, w) > max_side:
        s = max_side / max(h, w)
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes()


def _roster(db: Session, class_id: str) -> list[Student]:
    return list(db.scalars(select(Student).where(Student.class_id == class_id)))


def _sheet_for(db: Session, a: Assessment, student: Student) -> Sheet:
    """The student's paper record for this assessment (made at print time; made now if they joined later)."""
    sh = db.scalar(select(Sheet).where(Sheet.assessment_id == a.id, Sheet.student_id == student.id))
    if not sh:
        sh = Sheet(sheet_id=new_id("s", 10), short_code=f"MT-{len(sheets_of(db, a.id)) + 1:03d}",
                   assessment_id=a.id, student_id=student.id)
        db.add(sh)
        db.flush()
    return sh


def _attach(db: Session, sc: Scan, sheet: Sheet | None, replace: bool) -> Scan | None:
    """Make `sc` the student's live scan. A newer upload replaces an unconfirmed one; a CONFIRMED one is only
    replaced on request. Returns the confirmed scan that blocked it (sc then becomes a duplicate), else None."""
    existing = db.scalar(select(Scan).where(Scan.sheet_id == sheet.sheet_id, Scan.is_current.is_(True),
                                            Scan.id != sc.id)) if sheet else None
    if existing is not None:
        if existing.status == "accepted" and not replace:
            sc.sheet_id, sc.is_current, sc.status, sc.duplicate_of = sheet.sheet_id, False, "duplicate", existing.id
            return existing
        existing.is_current = False
        db.flush()
    sc.sheet_id = sheet.sheet_id if sheet else None
    sc.is_current, sc.duplicate_of = True, None
    if sc.status == "duplicate":
        sc.status = "needs_review"
    return None


def _commit(db: Session):
    try:
        db.commit()
    except IntegrityError:  # backstop: the database allows one live scan per student
        db.rollback()
        raise api_error(409, "scan_conflict", "Another scan for this student was saved at the same moment. "
                                              "Refresh the review queue.")


def _identity_warning(identity: dict, roll: str | None, cls: ClassRoom) -> list[dict]:
    status = identity.get("status")
    if status in IDENTITY_WARNINGS:
        return [{"code": f"roll_{status}", "message": IDENTITY_WARNINGS[status].format(roll=roll, cls=cls.name)}]
    if status == "matched" and not identity.get("exact"):
        return [{"code": "roll_loose_match", "message": f"Roll number written as {roll}; matched to the roster "
                                                       "ignoring leading zeros. Check the student."}]
    return []


@router.post("/assessments/{assessment_id}/scans")
def upload_scan(assessment_id: str, image: UploadFile = File(...), roll_number: str | None = Form(default=None),
                replace: bool = False, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    a = own_assessment(db, teacher, assessment_id)
    if a.status not in ("printed", "scanning", "confirmed"):
        raise api_error(409, "not_printed", "Print the papers before scanning.")
    if image.content_type and not image.content_type.startswith("image/"):
        raise api_error(415, "not_an_image", "That file isn't a photo. Upload a JPG or PNG of the paper.")
    data = image.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise api_error(413, "too_large", "That photo is over 15 MB. Retake it or send a smaller copy.")
    img = pipeline.decode_image(data)
    if img is None:
        raise api_error(400, "bad_image", "Couldn't open that photo. Try again with a JPG or PNG.")

    cls = db.get(ClassRoom, a.class_id)
    qs = serialize.questions_of(db, a.id)
    qids = [q.id for q in qs]
    qtypes = question_types([q.data for q in qs])
    scan_id = new_id("sc")
    page, quality = pipeline.locate(img)  # straightened page, or why not
    shown = page if page is not None else img
    warnings: list[dict] = []
    if page is None:
        warnings.append({"code": quality, "message": {
            "too_dark": "The photo is too dark to straighten. Check it carefully, or retake it in better light.",
            "too_blurry": "The photo is blurry. Check it carefully, or retake it holding the phone steady.",
        }.get(quality, "The four corner squares weren't all found. Check the photo, or retake it with the whole "
                       "page in view.")})
    bubble = pipeline.read_answers(page, len(qs), qtypes) if page is not None else None
    crops = omr.crops(page, len(qs), qtypes) if page is not None else None

    # 1. read the paper: Gemini first; the bubble reader cross-checks it and covers for it when it's unavailable
    read, extracted_by, roll_text = None, None, None
    if gemini.enabled():
        try:
            read = gemini_reader.extract(_jpeg(shown), title=a.title, class_name=cls.name,
                                         paper_code=paper_code(a.id), question_ids=qids, types=qtypes)
            extracted_by, roll_text = "gemini", read["roll_number"]
            warnings += read["warnings"]
        except gemini.GeminiError as exc:
            warnings.append({"code": "ai_output_invalid" if exc.kind == "bad_output" else "ai_unavailable",
                             "message": f"{exc.message} Read the roll number and answers from the photo below."})
    else:
        warnings.append({"code": "ai_off", "message": "Gemini isn't set up, so enter the roll number from the photo "
                                                     "and check every answer."})
    answers = []
    for i, (qid, qtype) in enumerate(zip(qids, qtypes)):
        g = read["answers"][i] if read else None
        b = bubble[i] if bubble else None
        if qtype == "descriptive":  # handwriting only: Gemini transcribes it, or the teacher types it from the photo
            ans = {k: g[k] for k in ("question_id", "detected", "state", "note", "text", "text_state")} if g else {
                "question_id": qid, "detected": None, "state": "unreadable", "text": "", "text_state": "not_read",
                "note": "Type the answer from the photo (handwriting wasn't read automatically)."}
            ans["type"] = "descriptive"
            ans["final"] = {"single": "answered", "blank": "blank"}.get(ans["state"])
            extracted_by = extracted_by or "manual"
        elif g is None and b is None:
            ans = {"question_id": qid, "detected": None, "state": "unreadable", "note": "Enter this answer from the photo."}
            extracted_by = extracted_by or "manual"
        elif g is None:
            ans = {"question_id": qid, "detected": b["detected"] if b["state"] == "single" else None,
                   "state": b["state"], "note": "Read by the bubble reader."}
            extracted_by = extracted_by or "bubble_reader"
        else:
            ans = {k: g[k] for k in ("question_id", "detected", "state", "note")}
            clear = ("single", "blank", "multiple")
            if b and g["state"] in clear and b["state"] in clear and (g["state"], g["detected"]) != (b["state"], b["detected"]):
                said = {"blank": "no mark", "multiple": "more than one mark"}
                ans.update(state="ambiguous", detected=None,
                           note=f"Gemini read {g['detected'] or said[g['state']]}, the bubble reader read "
                                f"{b['detected'] or said[b['state']]}. Check the photo.")
        if qtype != "descriptive":
            ans["final"] = ans["detected"] if ans["state"] == "single" else ("blank" if ans["state"] == "blank" else None)
            ans.setdefault("text", g.get("text", "") if g else "")
            ans.setdefault("text_state", g.get("text_state", "missing") if g else "not_read")
        ans["confidence"] = None  # model self-reports aren't calibrated; the teacher confirms instead
        if crops:
            ans["crop_url"] = _save(crops[i][0], f"{scan_id}_q{i + 1}.jpg")
            ans["reasoning_crop_url"] = _save(crops[i][1], f"{scan_id}_q{i + 1}_why.jpg")
        answers.append(ans)
    if any(x["state"] in ("multiple", "ambiguous", "unreadable") for x in answers) and extracted_by == "gemini":
        warnings.append({"code": "answers_unclear", "message": "Some answers are unclear. Choose them from the photo."})
    if any(x["text_state"] == "unclear" for x in answers):
        warnings.append({"code": "handwriting_unclear", "message": "Some handwriting couldn't be read with confidence. "
                                                                   "Compare the transcription with the photo and correct it."})

    # 2. who is it? the teacher's typed roll number wins; matching only looks at this assessment's class
    if roll_number and roll_number.strip():
        roll_text = rolls.normalize(roll_number)
    identity = rolls.match(roll_text, _roster(db, a.class_id))
    warnings = [w for w in warnings if w["code"] != "roll_unreadable"] + _identity_warning(identity, roll_text, cls)
    student = db.get(Student, identity["student_id"]) if identity["status"] == "matched" else None

    # 3. store it for review; one live scan per student
    sc = Scan(id=scan_id, assessment_id=a.id, status="needs_review", answers=answers, image_url=_save(shown, f"{scan_id}.jpg"),
              roll_number=roll_text, extracted_by=extracted_by, identity=identity, warnings=warnings)
    with _attach_lock:
        db.add(sc)
        sheet = _sheet_for(db, a, student) if student else None
        blocker = _attach(db, sc, sheet, replace)
        if blocker is not None:
            sc.warnings = warnings + [{"code": "already_confirmed", "message": f"{student.display_name} already has a "
                                       "confirmed paper. Choose Replace to use this photo instead."}]
        if a.status == "printed":
            a.status = "scanning"
        _commit(db)
    return serialize.scan(db, sc)


@router.get("/assessments/{assessment_id}/scans")
def scan_progress(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    a = own_assessment(db, teacher, assessment_id)
    total = len(sheets_of(db, a.id))
    current = current_scans(db, a.id)
    accepted = sum(1 for s in current if s.status == "accepted")
    review = sum(1 for s in current if s.status == "needs_review")
    recent = list(db.scalars(select(Scan).where(Scan.assessment_id == a.id, Scan.status.in_(("rejected", "duplicate")))
                             .order_by(Scan.created_at.desc()).limit(20)))
    live = {s.id for s in current}
    dups = [s for s in recent if s.status == "duplicate" and s.duplicate_of in live][:5]
    return {"total": total, "accepted": accepted, "needs_review": review,
            "remaining": max(total - sum(1 for s in current if s.sheet_id and s.status in ("accepted", "needs_review")), 0),
            "scans": [serialize.scan(db, s) for s in sorted(current, key=lambda s: s.created_at, reverse=True)],
            "duplicates": [serialize.scan(db, s) for s in dups],
            "rejected": [serialize.scan(db, s) for s in recent
                         if s.status == "rejected" and s.reject_reason != "discarded_by_teacher"][:5]}


class ReviewAnswer(BaseModel):
    question_id: str
    final: str | None = None  # A-D | blank for bubbles; answered | blank for written answers; None = keep
    text: str | None = None   # teacher's corrected transcription (reasoning, notes or the written answer)


class ReviewBody(BaseModel):
    answers: list[ReviewAnswer] = []
    confirmed: bool = True
    student_id: str | None = None   # the teacher picks the student...
    roll_number: str | None = None  # ...or types the roll number from the photo
    replace: bool = False           # use this paper even though the student already has a confirmed one
    discard: bool = False           # not a paper of this assessment: take it out of the queue
    base_version: int | None = None  # the scan version this edit started from (offline edits); stale -> 409 conflict


@router.patch("/scans/{scan_id}/review")
def review(scan_id: str, body: ReviewBody, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    sc = db.get(Scan, scan_id)
    if not sc:
        raise api_error(404, "not_found", "Scan not found.")
    a = own_assessment(db, teacher, sc.assessment_id)
    if body.base_version is not None and body.base_version != (sc.version or 1):
        raise api_error(409, "conflict", "This paper was changed somewhere else since you edited it. Check the newer "
                                         "version, then apply your change again.", current=serialize.scan(db, sc))
    if body.discard:
        sc.status, sc.reject_reason, sc.is_current = "rejected", "discarded_by_teacher", False
        db.commit()
        return serialize.scan(db, sc)
    if sc.status == "duplicate" and not body.replace:
        raise api_error(409, "already_confirmed", "This student already has a confirmed paper. "
                                                  "Choose Replace to use this photo instead.")
    if not sc.is_current and sc.status != "duplicate":
        raise api_error(409, "not_current", "This scan was replaced or discarded. Review the current one.")

    with _attach_lock:
        # identity: chosen student or typed roll number, always within the assessment's class
        student = None
        if body.student_id:
            student = db.get(Student, body.student_id)
            if not student or student.class_id != a.class_id:
                raise api_error(400, "wrong_class", "That student isn't in this assessment's class.")
            sc.identity = {"status": "matched", "student_id": student.id, "candidates": [student.id], "by": "teacher"}
        elif body.roll_number is not None:
            sc.roll_number = rolls.normalize(body.roll_number) or None
            sc.identity = rolls.match(sc.roll_number, _roster(db, a.class_id))
            if sc.identity["status"] != "matched":
                cls = db.get(ClassRoom, a.class_id)
                raise api_error(400, f"roll_{sc.identity['status']}", _identity_warning(sc.identity, sc.roll_number, cls)[0]["message"])
            student = db.get(Student, sc.identity["student_id"])
        if student is not None or (sc.status == "duplicate" and body.replace):
            if student is None:
                student = db.get(Student, db.get(Sheet, sc.sheet_id).student_id)
            blocker = _attach(db, sc, _sheet_for(db, a, student), body.replace)
            if blocker is not None:
                db.rollback()
                raise api_error(409, "already_confirmed", f"{student.display_name} already has a confirmed paper. "
                                                          "Choose Replace to use this photo instead.")
            sc.warnings = [w for w in (sc.warnings or []) if not w["code"].startswith("roll_") and w["code"] != "already_confirmed"]

        kinds = dict(zip([q.id for q in serialize.questions_of(db, a.id)],
                         question_types([q.data for q in serialize.questions_of(db, a.id)])))
        fixes, texts = {}, {}
        for x in body.answers:
            if x.text is not None:
                texts[x.question_id] = x.text.strip()[:4000]
            if x.final is None:
                continue
            v = x.final.strip().lower()
            v = v if v in ("blank", "answered") else v.upper()
            ok = ("answered", "blank") if kinds.get(x.question_id) == "descriptive" else ("A", "B", "C", "D", "blank")
            if v not in ok:
                raise api_error(400, "bad_answer", "Answers must be A, B, C, D or blank (written answers: answered or blank).")
            fixes[x.question_id] = v
        answers = []
        for x in sc.answers:
            x = dict(x)
            if x["question_id"] in fixes:
                x["final"], x["reviewed"] = fixes[x["question_id"]], True
            if x["question_id"] in texts:
                x["text"], x["text_state"], x["reviewed"] = texts[x["question_id"]], "teacher", True
                if x.get("type") == "descriptive":
                    x["note"] = ""  # the teacher's transcription replaces the reader's note
            answers.append(x)
        sc.answers = answers
        sc.version = (sc.version or 1) + 1
        if body.confirmed:
            if not sc.sheet_id or not sc.is_current:
                raise api_error(400, "no_student", "Choose the student (or enter the roll number) before confirming.")
            if any(x.get("final") is None for x in answers):
                raise api_error(400, "incomplete", "Choose an answer (or blank) for every flagged question.")
            sc.status = "accepted"
        _commit(db)
    return serialize.scan(db, sc)
