"""Roll-number + Gemini scanning: identity matching, uncertainty, failures, duplicates, uploads and access rules.
Gemini is faked (tests/conftest.py `gem`); photos are synthetic renders of the real printed PDF."""
from types import SimpleNamespace

import numpy as np
import pytest
from sqlalchemy.exc import IntegrityError

from app import gemini, rolls
from app.db import SessionLocal
from app.models import ClassRoom, Scan, Student, Teacher
from app.routes import scans as scans_route
from app.scanner.gemini_reader import validate
from app.security import hash_secret
from tests import synth
from tests.scanhelp import login, photo, printed, reading, review, upload

QIDS = ["q_1", "q_2", "q_3"]


# ---------------------------------------------------------------- roll numbers (pure)
def _roster(*rolls_):
    return [SimpleNamespace(id=f"st_{r}", roll_no=r, student_code=f"7A-{r}") for r in rolls_]


@pytest.mark.parametrize("written,status,student", [
    ("01", "matched", "st_01"), (" 0 1 ", "matched", "st_01"), ("7a-01", "matched", "st_01"),  # spacing, case, login code
    ("1", "matched", "st_01"),     # leading zero missing: the only possibility
    ("007", "matched", "st_07"),   # extra zeros
    ("12b", "matched", "st_12B"),  # alphanumeric
    ("99", "unknown", None), ("", "unreadable", None), (None, "unreadable", None),
])
def test_roll_matching(written, status, student):
    m = rolls.match(written, _roster("01", "02", "07", "12B"))
    assert m["status"] == status and m.get("student_id") == student


def test_roll_exact_match_wins_and_ambiguity_is_never_guessed():
    roster = _roster("1", "01")
    assert rolls.match("01", roster)["student_id"] == "st_01"  # exact beats loose
    amb = rolls.match("001", roster)                            # "1" and "01" are both possible
    assert amb["status"] == "ambiguous" and amb["candidates"] == ["st_01", "st_1"] and "student_id" not in amb


# ---------------------------------------------------------------- validating Gemini's reply (pure)
def _v(raw):
    return validate(raw, question_ids=QIDS, paper_code="ABC123", class_name="7A")


def test_validate_keeps_blank_multiple_unreadable_and_never_fills_in():
    out = _v(reading("04", ["", "AB", "?"], QIDS))
    assert [(a["state"], a["detected"]) for a in out["answers"]] == [("blank", None), ("multiple", None), ("unreadable", None)]
    assert out["roll_number"] == "04" and not out["warnings"]


def test_validate_flags_unclear_roll_and_wrong_paper():
    out = _v(reading("0?", ["B", "B", "B"], QIDS, legibility="unclear", code="ZZZ999", page=(2, 2), cls="8B",
                     warnings=["blurry", "made_up_warning"]))
    codes = [w["code"] for w in out["warnings"]]
    assert out["roll_number"] is None and out["roll_text"] == "0?"
    assert codes == ["roll_unreadable", "other_assessment", "page_mismatch", "class_mismatch", "blurry"]
    assert "Enter it manually or retake the photo" in out["warnings"][0]["message"]


def test_validate_turns_inconsistent_output_into_review_items():
    raw = reading("04", ["B", "B", "B"], QIDS)
    raw["answers"][0] = {"question_id": "q_1", "marked": ["A", "C"], "state": "single"}  # says single, two marks
    raw["answers"][1] = {"question_id": "q_x_not_ours", "marked": ["A"], "state": "single"}  # not this paper
    raw["answers"].append({"question_id": "q_3", "marked": ["D"], "state": "single"})        # q_3 read twice
    out = _v(raw)
    assert [a["state"] for a in out["answers"]] == ["ambiguous", "unreadable", "unreadable"]
    assert all(a["detected"] is None for a in out["answers"])
    assert "ai_inconsistent" in [w["code"] for w in out["warnings"]]


def test_validate_rejects_malformed_reply():
    for raw in ({}, {"answers": "nope"}, ["not", "a", "dict"]):
        with pytest.raises(gemini.GeminiError):
            _v(raw)


# ---------------------------------------------------------------- the scan route
@pytest.fixture
def paper(client, gem):
    H = login(client)
    aid, qids, pages, _ = printed(client, H)
    return SimpleNamespace(H=H, aid=aid, qids=qids, pages=pages, gem=gem)


def _up(client, p, roll, marks, i=0, **kw):
    p.gem["readings"].append(kw.pop("reply", None) or reading(roll, marks, p.qids))
    r = upload(client, p.H, p.aid, photo(p.pages[i], marks, seed=i), **kw)
    assert r.status_code == 200, r.text
    return r.json()


def test_unknown_roll_needs_the_teacher_then_confirms(client, paper):
    sc = _up(client, paper, "42", ["B", "B", "B"])
    assert sc["student"] is None and sc["roll_number"]["status"] == "unknown"
    assert any(w["code"] == "roll_unknown" for w in sc["warnings"])
    assert review(client, paper.H, sc["scan_id"], confirmed=True).json()["error"] == "no_student"
    assert review(client, paper.H, sc["scan_id"], roll_number="99", confirmed=True).json()["error"] == "roll_unknown"
    ok = review(client, paper.H, sc["scan_id"], roll_number="2", confirmed=True).json()
    assert ok["status"] == "accepted" and ok["student"]["display_name"] == "Diya"
    assert not any(w["code"].startswith("roll_") for w in ok["warnings"])


def test_gemini_unavailable_falls_back_to_bubble_reader_and_manual_roll(client, paper):
    sc = _up(client, paper, None, ["A", "B", "C"], reply=gemini.GeminiError("timeout", "Gemini took too long to answer."))
    assert sc["extracted_by"] == "bubble_reader" and sc["status"] == "needs_review" and sc["student"] is None
    assert [a["detected"] for a in sc["answers"]] == ["A", "B", "C"]
    assert {"ai_unavailable", "roll_unreadable"} <= {w["code"] for w in sc["warnings"]}
    ok = review(client, paper.H, sc["scan_id"], roll_number="03", confirmed=True).json()
    assert ok["status"] == "accepted" and ok["student"]["roll_no"] == "03"


def test_malformed_gemini_reply_is_labelled_and_reviewable(client, paper):
    sc = _up(client, paper, None, ["B", "B", "B"], reply={"roll_number": {"text": "04"}})
    assert sc["extracted_by"] == "bubble_reader"
    assert "ai_output_invalid" in {w["code"] for w in sc["warnings"]}


def test_gemini_and_bubble_reader_disagreeing_goes_to_review(client, paper):
    sc = _up(client, paper, "04", ["B", "B", "B"], reply=reading("04", ["C", "B", "B"], paper.qids))
    assert sc["answers"][0]["state"] == "ambiguous" and sc["answers"][0]["final"] is None
    assert "Gemini read C, the bubble reader read B" in sc["answers"][0]["note"]


def test_gemini_off_and_unreadable_photo_means_manual_entry_or_discard(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "AI_MODE", "fixtures")
    H = login(client)
    aid, qids, _, _ = printed(client, H)
    junk = synth.jpeg(np.full((600, 400, 3), 128, np.uint8))
    sc = upload(client, H, aid, junk, roll_number="05").json()  # teacher typed the roll number with the photo
    assert sc["extracted_by"] == "manual" and sc["student"]["display_name"] == "Rehan"
    assert {a["state"] for a in sc["answers"]} == {"unreadable"} and "ai_off" in {w["code"] for w in sc["warnings"]}
    assert review(client, H, sc["scan_id"], confirmed=True).json()["error"] == "incomplete"
    gone = review(client, H, sc["scan_id"], discard=True).json()
    assert gone["status"] == "rejected"
    assert client.get(f"/api/assessments/{aid}/scans", headers=H).json()["needs_review"] == 0


def test_newer_upload_replaces_an_unconfirmed_one(client, paper):
    first = _up(client, paper, "01", ["A", "B", "B"])
    second = _up(client, paper, "01", ["B", "B", "B"], i=0)
    prog = client.get(f"/api/assessments/{paper.aid}/scans", headers=paper.H).json()
    assert prog["needs_review"] == 1 and [s["scan_id"] for s in prog["scans"]] == [second["scan_id"]]
    assert review(client, paper.H, first["scan_id"], confirmed=True).json()["error"] == "not_current"


def test_database_allows_one_live_scan_per_student(client, paper):
    sc = _up(client, paper, "01", ["A", "B", "B"])
    db = SessionLocal()
    try:
        db.add(Scan(id="sc_race", assessment_id=paper.aid, sheet_id=sc["sheet_id"], status="needs_review",
                    answers=[], is_current=True))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------- uploads, classes and access
@pytest.fixture(scope="module")
def other_teacher():
    """A second teacher with class 8B, whose student ALSO has roll number 01."""
    db = SessionLocal()
    if not db.get(Teacher, "t_other"):
        db.add(Teacher(id="t_other", email="other@mindtrace.demo", name="Other", password_hash=hash_secret("pw123456")))
        db.add(ClassRoom(id="cl_8b", teacher_id="t_other", name="8B", grade="8"))
        db.add(Student(id="st_8b_01", class_id="cl_8b", display_name="Zoya", student_code="8B-01", roll_no="01",
                       pin_hash=hash_secret("9999")))
        db.commit()
    db.close()
    return "other@mindtrace.demo"


def test_same_roll_in_another_class_never_matches(client, paper, other_teacher):
    sc = _up(client, paper, "01", ["A", "B", "B"])
    assert sc["student"]["display_name"] == "Aarav"  # 7A's 01, not 8B's
    r = review(client, paper.H, sc["scan_id"], student_id="st_8b_01", confirmed=True)
    assert r.status_code == 400 and r.json()["error"] == "wrong_class"


def test_other_teachers_and_students_are_kept_out(client, paper, other_teacher):
    sc = _up(client, paper, "02", ["A", "B", "B"])
    H2 = login(client, other_teacher, "pw123456")
    jpg = photo(paper.pages[1], ["A", "B", "B"])
    assert upload(client, H2, paper.aid, jpg).status_code == 403
    assert review(client, H2, sc["scan_id"], confirmed=True).status_code == 403
    assert client.get(f"/api/assessments/{paper.aid}/scans", headers=H2).status_code == 403
    s = client.post("/api/auth/student/login", json={"student_code": "7A-02", "pin": "2222"}).json()
    SH = {"Authorization": f"Bearer {s['token']}"}
    assert upload(client, SH, paper.aid, jpg).status_code == 401
    assert review(client, SH, sc["scan_id"], confirmed=True).status_code == 401


def test_upload_validation(client, paper, monkeypatch):
    r = client.post(f"/api/assessments/{paper.aid}/scans", headers=paper.H,
                    files={"image": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 415 and r.json()["error"] == "not_an_image"
    r = client.post(f"/api/assessments/{paper.aid}/scans", headers=paper.H,
                    files={"image": ("broken.jpg", b"not really a jpeg", "image/jpeg")})
    assert r.status_code == 400 and r.json()["error"] == "bad_image"
    monkeypatch.setattr(scans_route, "MAX_UPLOAD_BYTES", 1000)
    r = upload(client, paper.H, paper.aid, photo(paper.pages[0], ["A", "B", "B"]))
    assert r.status_code == 413 and r.json()["error"] == "too_large"
    assert not paper.gem["calls"]  # nothing invalid ever reaches Gemini
