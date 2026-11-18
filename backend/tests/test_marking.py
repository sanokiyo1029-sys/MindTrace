"""Phase 2: the 17 question types, auto-marking with partial credit, teacher marks, pictures, and the printed paper.
All names are fictional."""
import cv2
import numpy as np
import pypdfium2 as pdfium
import pytest

from app import marking
from app.db import SessionLocal
from app.models import ClassRoom, Student
from app.security import hash_secret
from tests import synth
from tests.scanhelp import login, photo, review, upload

CLS = "cl_mark"
OPTS = {"A": "4 N", "B": "8 N", "C": "2 N", "D": "16 N"}
EXAMPLES = {  # one valid question per type
    "mcq": {"stem": "A 2 kg mass accelerates at 4 m/s². Net force?", "options": OPTS, "answer": "B",
            "distractors": {k: {"misconception_id": "M_ADD_DENOMS", "why": "x"} for k in "ACD"}},
    "multi_select": {"stem": "Which are vectors?", "options": {"A": "Speed", "B": "Velocity", "C": "Force", "D": "Mass"},
                     "answers": ["B", "C"], "marks": 2},
    "true_false": {"stem": "Light travels faster than sound.", "answer": "A"},
    "fill_blank": {"stem": "Plants make food by ___ using ___.", "blanks": [["photosynthesis"], ["sunlight", "light"]]},
    "match": {"stem": "Match the unit to the quantity.", "pairs": [["Force", "newton"], ["Energy", "joule"], ["Power", "watt"]],
              "marks": 3},
    "assertion_reason": {"stem": "Assertion: Ice floats on water. Reason: Ice is less dense than water.", "answer": "A"},
    "one_word": {"stem": "The powerhouse of the cell?", "accepted": ["mitochondria", "mitochondrion"]},
    "short": {"stem": "Why do we see lightning before thunder?", "marks": 2, "model_answer": "Light is faster."},
    "long": {"stem": "Explain the water cycle.", "marks": 5},
    "essay": {"stem": "Should cities ban petrol cars? Use science in your answer.", "marks": 10},
    "maths": {"stem": "Simplify 3/4 + 1/8.", "value": "7/8", "marks": 2},
    "numerical": {"stem": "A car covers 100 m in 8 s. Speed?", "value": 12.5, "tolerance": 0.1, "unit": "m/s", "marks": 2},
    "diagram": {"stem": "Draw and label a simple electric circuit with a cell, switch and bulb.", "marks": 3},
    "image": {"stem": "Which organ is shown in the picture?", "options": {"A": "Heart", "B": "Lung"}, "answer": "A"},
    "programming": {"stem": "Write a function that returns the larger of two numbers.", "marks": 4},
    "code": {"stem": "What does this print?", "code": "x = 3\nprint(x * 2)", "accepted": ["6"]},
    "graph": {"stem": "From the graph, what is the speed at t = 4 s (m/s)?", "value": 10, "tolerance": 0.5},
}


def test_every_type_validates_and_has_a_paper_kind():
    assert set(EXAMPLES) | {"descriptive"} == set(marking.TYPES) and len(EXAMPLES) == 17
    for t, q in EXAMPLES.items():
        q = {"type": t, **q}
        assert marking.validate(q) == [] or t == "mcq", (t, marking.validate(q))
        assert marking.paper_kind(q) in ("mcq", "descriptive")
    bubble = {t for t, q in EXAMPLES.items() if marking.paper_kind({"type": t, **q}) == "mcq"}
    assert bubble == {"mcq", "true_false", "assertion_reason", "image"}
    # broken questions say what to fix
    assert "Tick at least one correct option." in marking.validate({"type": "multi_select", "stem": "x", "options": OPTS})
    assert "Give 2 to 6 complete pairs." in marking.validate({"type": "match", "stem": "x", "pairs": [["a", "b"]]})
    assert "Give the correct numerical answer." in marking.validate({"type": "numerical", "stem": "x"})
    assert "Marks must be a number from 0.5 to 20." in marking.validate({"type": "short", "stem": "x", "marks": 50})
    assert marking.validate({"type": "quiz", "stem": "x"}) == ["Unknown question type 'quiz'."]


def test_auto_marking_with_partial_credit():
    q = lambda t: {"type": t, **EXAMPLES[t]}  # noqa: E731
    assert marking.mark(q("mcq"), "B") == 1 and marking.mark(q("mcq"), "A") == 0
    assert marking.mark(q("multi_select"), ["B", "C"]) == 2
    assert marking.mark(q("multi_select"), "B") == 1                 # half right
    assert marking.mark(q("multi_select"), "A, B, C") == 1           # a wrong tick cancels a right one
    assert marking.mark(q("multi_select"), ["A", "D"]) == 0          # never below zero
    assert marking.mark(q("true_false"), "A") == 1
    assert marking.mark(q("fill_blank"), "Photosynthesis\nlight") == 1
    assert marking.mark(q("fill_blank"), "photosynthesis, water") == 0.5
    labels = marking.match_choices(q("match"))
    letter = {r: "ABC"[i] for i, r in enumerate(labels)}
    assert marking.mark(q("match"), f"1-{letter['newton']}, 2-{letter['joule']} 3:{letter['watt']}") == 3
    assert marking.mark(q("match"), {1: "newton", 2: "watt", 3: "joule"}) == 1   # online answers by text
    assert marking.mark(q("one_word"), " Mitochondria. ") == 1
    assert marking.mark(q("numerical"), "v = 12.48 m/s") == 2 and marking.mark(q("numerical"), "12.7") == 0
    assert marking.mark(q("maths"), "7/8") == 2 and marking.mark(q("maths"), "0.875") == 2
    assert marking.mark(q("code"), "6") == 1 and marking.mark(q("graph"), "about 10.4") == 1
    for t in ("short", "long", "essay", "diagram", "programming"):
        assert marking.mark(q(t), "anything") is None                 # the teacher marks these
    assert marking.mark(q("numerical"), "") == 0
    # a scanned answer: teacher's mark wins; unread handwriting waits for the teacher
    assert marking.answer_score(q("numerical"), {"final": "answered", "text": "12.5", "text_state": "not_read"}) is None
    assert marking.answer_score(q("numerical"), {"final": "answered", "text": "12.5", "text_state": "teacher"}) == 2
    assert marking.answer_score(q("short"), {"final": "answered", "teacher_score": 1.5}) == 1.5
    assert marking.answer_score(q("short"), {"final": "blank"}) == 0


@pytest.fixture(scope="module", autouse=True)
def marking_class(client):  # client first: it creates the tables
    with SessionLocal() as db:
        if not db.get(ClassRoom, CLS):
            db.add(ClassRoom(id=CLS, teacher_id="t_demo", name="8M", grade="8"))
            for i, name in enumerate(["Uma", "Vik"], start=1):
                db.add(Student(id=f"st_8m_0{i}", class_id=CLS, display_name=name, student_code=f"8M-0{i}",
                               roll_no=f"0{i}", pin_hash=hash_secret("4321")))
            db.commit()


def _draft(client, H):
    a = client.post("/api/assessments/generate", headers=H, json={"class_id": CLS, "num_questions": 1}).json()
    return a["id"]


def _add(client, H, aid, t):
    r = client.post(f"/api/assessments/{aid}/questions", headers=H, json={"type": t, **EXAMPLES[t]})
    assert r.status_code == 200, r.text
    return r.json()["questions"][-1]


def _png():
    img = np.full((120, 200, 3), 255, np.uint8)
    cv2.circle(img, (100, 60), 40, (40, 40, 200), -1)
    return cv2.imencode(".png", img)[1].tobytes()


def test_every_type_can_be_added_approved_and_printed(client):
    H = login(client)
    types = [t for t in EXAMPLES if t != "mcq"]
    assert client.post(f"/api/assessments/{_draft(client, H)}/questions", headers=H,
                       json={"type": "quiz", "stem": "x"}).json()["error"] == "bad_type"
    for chunk in (types[i:i + 4] for i in range(0, len(types), 4)):  # 4 + the drafted MCQ = 5 per paper
        aid = _draft(client, H)
        for t in chunk:
            q = _add(client, H, aid, t)
            assert q["type"] == t
        r = client.post(f"/api/assessments/{aid}/approve", headers=H)
        assert r.json()["status"] == "approved", r.text
        pdf = client.get(f"/api/assessments/{aid}/print", headers=H)
        assert pdf.status_code == 200
        text = pdfium.PdfDocument(pdf.content)[0].get_textpage().get_text_range()
        if "match" in chunk:
            assert "Write pairs like 1-B, 2-A." in text and "1. Force" in text
        if "code" in chunk:
            assert "print(x * 2)" in text
        if "true_false" in chunk:
            assert "True" in text and "False" in text
    # an invalid question blocks approval with the reason
    aid = _draft(client, H)
    client.post(f"/api/assessments/{aid}/questions", headers=H, json={"type": "numerical", "stem": "Speed?"})
    bad = client.post(f"/api/assessments/{aid}/approve", headers=H).json()
    assert bad["error"] == "invalid_questions" and "Give the correct numerical answer." in str(bad["questions"])


def test_question_picture_upload_print_and_access(client):
    H = login(client)
    aid = _draft(client, H)
    q = _add(client, H, aid, "image")
    assert client.post(f"/api/questions/{q['id']}/image", headers=H,
                       files={"image": ("x.png", b"not an image", "image/png")}).json()["error"] == "bad_image"
    q = client.post(f"/api/questions/{q['id']}/image", headers=H, files={"image": ("x.png", _png(), "image/png")}).json()
    url = q["image_url"]
    assert url.startswith("/api/media/questions/") and client.get(url, headers=H).status_code == 200
    stranger = client.post("/api/auth/teacher/signup", json={"name": "Ms Other", "email": "other.mark@example.com",
                                                              "password": "other2026x"}).json()["token"]
    assert client.get(url, headers={"Authorization": f"Bearer {stranger}"}).status_code == 403
    student = client.post("/api/auth/student/login", json={"student_code": "8M-01", "pin": "4321"}).json()["token"]
    assert client.get(url, headers={"Authorization": f"Bearer {student}"}).status_code == 200  # a student of 8M
    # replacing the picture removes the old file
    newer = client.post(f"/api/questions/{q['id']}/image", headers=H, files={"image": ("y.png", _png(), "image/png")}).json()
    assert newer["image_url"] != url and client.get(url, headers=H).status_code == 404
    assert client.post(f"/api/assessments/{aid}/approve", headers=H).json()["status"] == "approved"
    assert client.get(f"/api/assessments/{aid}/print", headers=H).status_code == 200  # picture drawn on the sheet
    assert client.delete(f"/api/questions/{q['id']}/image", headers=H).json()["error"] == "already_printed"


def test_scanned_paper_auto_marks_and_teacher_gives_partial_credit(client):
    H = login(client)
    aid = _draft(client, H)
    for t in ("numerical", "match", "short", "true_false"):
        _add(client, H, aid, t)
    a = client.post(f"/api/assessments/{aid}/approve", headers=H).json()
    qs = {q["type"]: q for q in a["questions"]}
    kinds = [marking.paper_kind(q) for q in a["questions"]]
    assert kinds == ["mcq", "descriptive", "descriptive", "descriptive", "mcq"]
    pages = synth.render_pages(client.get(f"/api/assessments/{aid}/print", headers=H).content)
    marks = [qs["mcq"]["answer"], "", "", "", "B"]  # right MCQ, wrong True/False
    sc = upload(client, H, aid, photo(pages[0], marks, n=5, types=kinds), roll_number="01").json()
    assert sc["student"]["display_name"] == "Uma" and sc["max_score"] == 1 + 2 + 3 + 2 + 1
    letter = {r: "ABC"[i] for i, r in enumerate(marking.match_choices(qs["match"]))}
    written = [
        {"question_id": qs["numerical"]["id"], "final": "answered", "text": "s = d/t = 12.5 m/s"},
        {"question_id": qs["match"]["id"], "final": "answered",
         "text": f"1-{letter['newton']} 2-{letter['watt']} 3-{letter['joule']}"},       # 1 of 3 pairs right
        {"question_id": qs["short"]["id"], "final": "answered", "text": "Light is faster than sound."},
    ]
    saved = review(client, H, sc["scan_id"], confirmed=False, answers=written).json()
    by_q = {x["question_id"]: x for x in saved["answers"]}
    assert by_q[qs["numerical"]["id"]]["score"] == 2 and by_q[qs["numerical"]["id"]]["scored_by"] == "auto"
    assert by_q[qs["match"]["id"]]["score"] == 1
    assert by_q[qs["short"]["id"]]["score"] is None and saved["to_mark"] == 1
    assert review(client, H, sc["scan_id"], confirmed=False, answers=[
        {"question_id": qs["short"]["id"], "score": 5}]).json()["error"] == "bad_score"
    done = review(client, H, sc["scan_id"], answers=[{"question_id": qs["short"]["id"], "score": 1.5},
                                                     {"question_id": qs["match"]["id"], "score": 2}]).json()
    assert done["status"] == "accepted" and done["to_mark"] == 0
    assert done["score"] == 1 + 2 + 2 + 1.5 + 0  # the teacher raised match to 2
    # back to auto-marking when the teacher clears their mark
    back = review(client, H, sc["scan_id"], answers=[{"question_id": qs["match"]["id"], "score": None}]).json()
    assert back["score"] == 5.5
    row = next(r for r in client.get(f"/api/assessments/{aid}/results", headers=H).json() if r["roll_no"] == "01")
    assert (row["score"], row["max_score"], row["to_mark"]) == (5.5, 9, 0)
    assert (row["correct"], row["total"]) == (1, 2)  # bubble questions only, as before
    assert {x["scored_by"] for x in row["answers"]} == {"auto", "teacher"}
    # the student sees their marks once the paper is released
    assert client.post(f"/api/assessments/{aid}/confirm", headers=H).status_code == 200
    S = {"Authorization": "Bearer " + client.post("/api/auth/student/login", json={"student_code": "8M-01", "pin": "4321"}).json()["token"]}
    mine = next(r for r in client.get("/api/student/me/results", headers=S).json()["assessments"] if r["assessment_id"] == aid)
    assert mine["score"]["score"] == 5.5 and mine["score"]["correct"] == 1
    assert mine["score"]["max_score"] == 9 and {x["max_score"] for x in mine["answers"]} == {1, 2, 3}


def test_layout_keeps_bubble_questions_readable_and_all_bubble_papers_unchanged():
    from app.layout import question_blocks
    assert [round(b["height"], 1) for b in question_blocks(5)] == [41.2] * 5  # same as before Phase 2
    mixed = question_blocks(5, ["mcq", "descriptive", "descriptive", "descriptive", "mcq_picture"])
    assert round(mixed[0]["height"], 1) == 41.2 and round(sum(b["height"] for b in mixed), 1) == 206
    assert mixed[4]["height"] > mixed[1]["height"] and mixed[4]["bubbles"] and not mixed[1]["bubbles"]
