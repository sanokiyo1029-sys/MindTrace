import cv2
from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import serialize
from app.config import MEDIA_DIR
from app.db import get_db
from app.errors import api_error
from app.ids import new_id
from app.models import Assessment, Scan, Sheet, Teacher
from app.routes.common import current_scans, own_assessment, sheets_of
from app.scanner import omr, pipeline
from app.security import current_teacher

router = APIRouter(prefix="/api", tags=["scans"])
SCAN_DIR = MEDIA_DIR / "scans"


def _save(img, name: str, max_side: int = 1600) -> str:
    h, w = img.shape[:2]
    if max(h, w) > max_side:
        s = max_side / max(h, w)
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(SCAN_DIR / name), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return f"/api/media/scans/{name}"


def _reject(db: Session, a: Assessment, scan_id: str, reason: str, img, sheet_id: str | None = None) -> dict:
    sc = Scan(id=scan_id, assessment_id=a.id, sheet_id=sheet_id, status="rejected", reject_reason=reason,
              answers=[], image_url=_save(img, f"{scan_id}.jpg") if img is not None else None, is_current=False)
    db.add(sc)
    db.commit()
    return serialize.scan(db, sc)


@router.post("/assessments/{assessment_id}/scans")
async def upload_scan(assessment_id: str, image: UploadFile = File(...), short_code: str | None = Form(default=None),
                      replace: bool = False, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    a = own_assessment(db, teacher, assessment_id)
    if a.status not in ("printed", "scanning", "confirmed"):
        raise api_error(409, "not_printed", "Print the sheets before scanning.")
    scan_id = new_id("sc")
    img = pipeline.decode_image(await image.read())
    if img is None:
        return _reject(db, a, scan_id, "page_not_found", None)

    page, sid, reason = pipeline.locate(img)
    sheet = db.get(Sheet, sid) if sid else None
    if sheet is None and short_code:  # QR unreadable: teacher typed the printed code
        sheet = db.scalar(select(Sheet).where(Sheet.assessment_id == a.id, Sheet.short_code == short_code.strip().upper()))
    if sid and (sheet is None or sheet.assessment_id != a.id):
        return _reject(db, a, scan_id, "unknown_sheet", img)
    if sheet is None:
        return _reject(db, a, scan_id, reason or "qr_not_found", img)
    if page is None:  # we know whose sheet it is, but can't read the bubbles reliably
        return _reject(db, a, scan_id, reason or "page_not_found", img, sheet.sheet_id)

    existing = db.scalar(select(Scan).where(Scan.sheet_id == sheet.sheet_id, Scan.is_current.is_(True)))
    if existing and not replace:
        sc = Scan(id=scan_id, assessment_id=a.id, sheet_id=sheet.sheet_id, status="duplicate",
                  duplicate_of=existing.id, answers=existing.answers, image_url=existing.image_url, is_current=False)
        db.add(sc)
        db.commit()
        return serialize.scan(db, sc)

    qs = serialize.questions_of(db, a.id)
    reads = pipeline.read_answers(page, len(qs))
    crops = omr.crops(page, len(qs))
    answers = []
    for i, (q, r) in enumerate(zip(qs, reads)):
        row, why = crops[i]
        answers.append({
            "question_id": q.id, "detected": r["detected"], "state": r["state"], "confidence": r["confidence"],
            "fill": r["fill"],
            "final": r["detected"] if r["state"] == "single" else ("blank" if r["state"] == "blank" else None),
            "crop_url": _save(row, f"{scan_id}_q{i + 1}.jpg"),
            "reasoning_crop_url": _save(why, f"{scan_id}_q{i + 1}_why.jpg"),
        })
    clear = all(x["state"] == "single" for x in answers)
    if existing:  # explicit re-scan replaces the old one
        existing.is_current = False
    sc = Scan(id=scan_id, assessment_id=a.id, sheet_id=sheet.sheet_id, status="accepted" if clear else "needs_review",
              answers=answers, image_url=_save(page, f"{scan_id}.jpg"), is_current=True)
    db.add(sc)
    if a.status == "printed":
        a.status = "scanning"
    db.commit()
    return serialize.scan(db, sc)


@router.get("/assessments/{assessment_id}/scans")
def scan_progress(assessment_id: str, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    a = own_assessment(db, teacher, assessment_id)
    total = len(sheets_of(db, a.id))
    current = current_scans(db, a.id)
    latest_ok = {s.sheet_id: s.created_at for s in current}
    rejected = [s for s in db.scalars(select(Scan).where(Scan.assessment_id == a.id, Scan.status == "rejected")
                                      .order_by(Scan.created_at.desc()))
                if not (s.sheet_id and s.sheet_id in latest_ok and latest_ok[s.sheet_id] > s.created_at)][:5]
    accepted = sum(1 for s in current if s.status == "accepted")
    review = sum(1 for s in current if s.status == "needs_review")
    return {"total": total, "accepted": accepted, "needs_review": review, "remaining": max(total - accepted - review, 0),
            "scans": [serialize.scan(db, s) for s in sorted(current, key=lambda s: s.created_at, reverse=True)],
            "rejected": [serialize.scan(db, s) for s in rejected]}


class ReviewAnswer(BaseModel):
    question_id: str
    final: str


class ReviewBody(BaseModel):
    answers: list[ReviewAnswer] = []
    confirmed: bool = True


@router.patch("/scans/{scan_id}/review")
def review(scan_id: str, body: ReviewBody, teacher: Teacher = Depends(current_teacher), db: Session = Depends(get_db)):
    sc = db.get(Scan, scan_id)
    if not sc:
        raise api_error(404, "not_found", "Scan not found.")
    own_assessment(db, teacher, sc.assessment_id)
    if not sc.is_current:
        raise api_error(409, "not_current", "This scan was replaced or rejected. Review the current one.")
    fixes = {x.question_id: x.final.strip().upper() if x.final.lower() != "blank" else "blank" for x in body.answers}
    bad = [v for v in fixes.values() if v not in ("A", "B", "C", "D", "blank")]
    if bad:
        raise api_error(400, "bad_answer", "Answers must be A, B, C, D or blank.")
    answers = []
    for x in sc.answers:
        x = dict(x)
        if x["question_id"] in fixes:
            x["final"] = fixes[x["question_id"]]
            x["reviewed"] = True
        answers.append(x)
    sc.answers = answers
    if body.confirmed:
        if any(x.get("final") is None for x in answers):
            raise api_error(400, "incomplete", "Choose an answer (or blank) for every flagged question.")
        sc.status = "accepted"
    db.commit()
    return serialize.scan(db, sc)
