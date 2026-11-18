"""Mixed MCQ + written-answer papers, handwriting review, teacher-approved feedback, subjects, practice, privacy,
offline-edit conflicts and session expiry. Gemini is faked; photos are synthetic renders of the real PDF."""
import pypdfium2 as pdfium
import pytest

from app import ai_bridge, config, gemini
from app.subject_data import SUBJECTS
from tests import synth
from tests.scanhelp import login, photo, review, upload

TYPES = ["mcq", "mcq", "descriptive"]


def _student(client, code, pin):
    r = client.post("/api/auth/student/login", json={"student_code": code, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _mixed(client, H, subject="physics"):
    a = client.post("/api/assessments/generate", headers=H, json={
        "class_id": "cl_7a", "subject": subject, "topic": "forces", "concepts_text": "F = ma", "num_questions": 3,
        "num_descriptive": 1}).json()
    assert [q["type"] for q in a["questions"]] == TYPES and a["subject"] == subject
    assert client.post(f"/api/assessments/{a['id']}/approve", headers=H).json()["status"] == "approved"
    pdf = client.get(f"/api/assessments/{a['id']}/print", headers=H)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    return a, synth.render_pages(pdf.content), pdf.content


def _reading(roll, qids, mcq, written, writing="clear", reason="because a = F/m"):
    ans = [{"question_id": q, "marked": [m], "state": "single", "written_text": reason, "writing": "clear"}
           for q, m in zip(qids[:2], mcq)]
    ans.append({"question_id": qids[2], "marked": [], "state": "single" if written else "blank",
                "written_text": written, "writing": writing})
    return {"roll_number": {"text": roll, "legibility": "clear"}, "class_section": "7A", "paper_code": "",
            "page": {"number": 1, "of": 1}, "answers": ans, "warnings": []}


def test_mixed_pdf_layout_and_pagination(client):
    H = login(client)
    a, pages, pdf = _mixed(client, H)
    doc = pdfium.PdfDocument(pdf)
    assert len(doc) == len(pages) == 5  # one single-page paper per student of 7A
    text = doc[0].get_textpage().get_text_range()
    assert "Write your answer here" in text and "Why did you choose this answer?" in text and "Page 1 of 1" in text
    # empty approval / nothing to print is refused with a reason, never an empty file
    empty = client.post("/api/assessments/generate", headers=H, json={"class_id": "cl_7a", "num_questions": 1}).json()
    assert client.get(f"/api/assessments/{empty['id']}/print", headers=H).json()["error"] == "not_approved"


def test_scan_mixed_paper_unclear_handwriting_correction_and_conflict(client, gem):
    H = login(client)
    a, pages, _ = _mixed(client, H)
    qids = [q["id"] for q in a["questions"]]
    gem["readings"].append(_reading("01", qids, ["A", "B"], "a book [?] forces", writing="unclear"))
    r = upload(client, H, a["id"], photo(pages[0], ["A", "B", ""], types=TYPES))
    sc = r.json()
    assert r.status_code == 200 and sc["status"] == "needs_review"
    desc = sc["answers"][2]
    assert desc["type"] == "descriptive" and desc["state"] == "unreadable" and desc["final"] is None
    assert desc["text_state"] == "unclear" and desc["crop_url"]  # original handwriting kept next to the transcription
    assert sc["answers"][0]["text"] == "because a = F/m"  # reasoning transcribed for MCQ too
    assert {w["code"] for w in sc["warnings"]} >= {"answers_unclear", "handwriting_unclear"}
    # bubble reader cross-checked the MCQ answers on the mixed layout
    assert [x["final"] for x in sc["answers"][:2]] == ["A", "B"]
    # can't confirm until the written answer is decided; a bad value is refused
    assert review(client, H, sc["scan_id"], confirmed=True).json()["error"] == "incomplete"
    assert review(client, H, sc["scan_id"], answers=[{"question_id": qids[2], "final": "C"}]).status_code == 400
    # teacher transcribes (draft save), which survives a reload
    v = sc["version"]
    saved = review(client, H, sc["scan_id"], confirmed=False, base_version=v, answers=[
        {"question_id": qids[2], "final": "answered", "text": "Weight pulls down and the table pushes up."}]).json()
    assert saved["status"] == "needs_review" and saved["version"] == v + 1
    again = [s for s in client.get(f"/api/assessments/{a['id']}/scans", headers=H).json()["scans"]
             if s["scan_id"] == sc["scan_id"]][0]
    assert again["answers"][2]["text"].startswith("Weight") and again["answers"][2]["text_state"] == "teacher"
    # a stale offline edit is refused, never silently overwrites
    stale = review(client, H, sc["scan_id"], base_version=v, answers=[{"question_id": qids[0], "final": "C"}])
    assert stale.status_code == 409 and stale.json()["error"] == "conflict" and stale.json()["current"]["version"] == v + 1
    assert review(client, H, sc["scan_id"], confirmed=True, base_version=v + 1).json()["status"] == "accepted"


def test_feedback_ai_failure_too_unclear_approval_and_student_privacy(client, gem):
    H = login(client)
    a, pages, _ = _mixed(client, H)
    qids = [q["id"] for q in a["questions"]]
    papers = {"01": (["B", "B"], "The book needs a force to keep it still."), "02": (["A", "B"], "")}
    ids = {}
    for i, (roll, (mcq, text)) in enumerate(papers.items()):
        gem["readings"].append(_reading(roll, qids, mcq, text))
        sc = upload(client, H, a["id"], photo(pages[i], mcq + [""], types=TYPES, seed=i)).json()
        ids[roll] = sc["scan_id"]
        assert review(client, H, sc["scan_id"], confirmed=True).json()["status"] == "accepted"
    # Aarav (01): one wrong MCQ (library suggestion) + one written answer; Diya (02): all bubbles right, no writing
    fb = client.get(f"/api/assessments/{a['id']}/feedback", headers=H).json()
    mine = [f for f in fb["items"] if f["student"]["roll_no"] == "01"]
    assert {f["question_type"] for f in mine} == {"mcq", "descriptive"}
    assert all(f["status"] == "pending" for f in fb["items"]) and not [f for f in fb["items"] if f["student"]["roll_no"] == "02"]

    # AI fails -> recorded, manual stays possible
    def boom(*a, **k):
        raise gemini.GeminiError("timeout", "Gemini took too long to answer.")
    gem_ask = gemini.ask
    gemini.ask = boom
    try:
        out = client.post(f"/api/assessments/{a['id']}/feedback/suggest", headers=H).json()
    finally:
        gemini.ask = gem_ask
    written = [f for f in out["items"] if f["question_type"] == "descriptive"][0]
    assert written["suggestion"]["state"] == "unavailable" and written["text"] == ""
    assert client.patch(f"/api/feedback/{written['id']}", headers=H, json={"status": "approved"}).json()["error"] == "empty_feedback"
    # AI works -> a suggestion the teacher edits, then approves
    gemini.ask = lambda *a, **k: {"misconception_id": "M_PHY_FORCE_MOTION", "label": "x",
                                  "feedback": "Try drawing the two forces as arrows."}
    try:
        out = client.post(f"/api/assessments/{a['id']}/feedback/suggest", headers=H).json()
    finally:
        gemini.ask = gem_ask
    written = [f for f in out["items"] if f["question_type"] == "descriptive"][0]
    assert written["suggestion"]["state"] == "ok" and written["suggestion"]["misconception_id"] == "M_PHY_FORCE_MOTION"
    ok = client.patch(f"/api/feedback/{written['id']}", headers=H, json={
        "text": "Try drawing the two forces on the book as arrows.", "status": "approved",
        "video_url": "https://example.org/forces.mp4"}).json()
    assert ok["status"] == "approved"
    assert client.patch(f"/api/feedback/{written['id']}", headers=H, json={"video_url": "javascript:alert(1)"}).status_code == 400

    S1, S2 = _student(client, "7A-01", "1111"), _student(client, "7A-02", "2222")
    # not released until the teacher confirms the assessment
    row = [x for x in client.get("/api/student/me/results", headers=S1).json()["assessments"] if x["assessment_id"] == a["id"]][0]
    assert row["status"] == "awaiting_review" and row["answers"] == [] and "feedback" not in row
    assert client.get(f"/api/media/scans/{ids['01']}.jpg", headers=S1).status_code == 403
    assert client.post(f"/api/assessments/{a['id']}/confirm", headers=H).json()["status"] == "confirmed"
    row = [x for x in client.get("/api/student/me/results", headers=S1).json()["assessments"] if x["assessment_id"] == a["id"]][0]
    assert row["status"] == "released" and row["score"].items() >= {"correct": 1, "total": 2}.items()  # bubbles: as before
    assert (row["score"]["score"], row["score"]["to_mark"]) == (1, 1)  # written answer waits for the teacher's mark
    assert [f["text"] for f in row["feedback"]] == ["Try drawing the two forces on the book as arrows."]  # pending MCQ hidden
    assert row["feedback"][0]["video_url"] == "https://example.org/forces.mp4"
    # own scan yes; a classmate's scan, without a token, or via the teacher API: no
    assert client.get(row["scan_url"], headers=S1).status_code == 200
    assert client.get(f"{row['scan_url']}").status_code == 401
    assert client.get(row["scan_url"], headers=S2).status_code == 403
    assert client.get(f"/api/assessments/{a['id']}/results", headers=S1).status_code == 401
    assert client.get("/api/students/st_02/report", headers=S1).status_code == 401
    other = [x for x in client.get("/api/student/me/results", headers=S2).json()["assessments"] if x["assessment_id"] == a["id"]][0]
    assert other["feedback"] == [] and "force to keep" not in str(other)


def test_each_subject_reaches_generation_and_bad_replies_fall_back(client, monkeypatch):
    monkeypatch.setattr(config, "AI_MODE", "live")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    seen = []

    def fake(system, prompt, schema, temperature=0.4, image_jpeg=None):
        seen.append((system, prompt, schema))
        return {"questions": []} if len(seen) % 2 else {"questions": [{"stem": "", "options": {}}]}  # empty / invalid
    monkeypatch.setattr(gemini, "ask", fake)
    H = login(client)
    for subject in SUBJECTS:
        start = len(seen)
        r = client.post("/api/assessments/generate", headers=H, json={
            "class_id": "cl_7a", "subject": subject, "topic": "t", "concepts_text": "c", "num_questions": 2,
            "difficulty": "easy"}).json()
        assert r["subject"] == subject and all(q["source"] == "sample" and q["subject"] == subject for q in r["questions"])
        assert r["notes"] and "sample" in r["notes"][0]
        assert subject.lower() in seen[start][0].lower() and "Difficulty: easy" in seen[start][1]
        ids = seen[start][2]["properties"]["questions"]["items"]["properties"]["distractors"]["items"]["properties"]["misconception_id"]["enum"]
        assert ids and all(ai_bridge.misconception_library()[i].get("subject", "mathematics") == subject for i in ids)
        aid = r["id"]
        assert client.post(f"/api/assessments/{aid}/approve", headers=H).json()["status"] == "approved"
    assert client.post("/api/assessments/generate", headers=H, json={"class_id": "cl_7a", "subject": "history"}).json()["error"] == "bad_subject"


def test_question_edit_conflict_and_teacher_added_question(client):
    H = login(client)
    a = client.post("/api/assessments/generate", headers=H, json={"class_id": "cl_7a", "num_questions": 2}).json()
    q = a["questions"][0]
    assert client.patch(f"/api/questions/{q['id']}", headers=H, json={"concept": "x", "base_version": 1}).json()["version"] == 2
    r = client.patch(f"/api/questions/{q['id']}", headers=H, json={"concept": "y", "base_version": 1})
    assert r.status_code == 409 and r.json()["current"]["concept"] == "x"
    a = client.post(f"/api/assessments/{a['id']}/questions", headers=H, json={"stem": "Explain your method."}).json()
    assert a["questions"][-1]["type"] == "descriptive" and a["questions"][-1]["source"] == "teacher"
    assert client.post(f"/api/assessments/{a['id']}/approve", headers=H).json()["status"] == "approved"


def test_assigned_practice_once_per_student_and_overview(client):
    H = login(client)
    a = client.post("/api/assessments/generate", headers=H, json={"class_id": "cl_7a", "num_questions": 2}).json()
    assert client.post(f"/api/assessments/{a['id']}/assign", headers=H).json()["error"] == "not_approved"
    client.post(f"/api/assessments/{a['id']}/approve", headers=H)
    st = client.post(f"/api/assessments/{a['id']}/assign", headers=H).json()
    assert st["assigned"] and {s["status"] for s in st["students"]} == {"not_started"}
    S = _student(client, "7A-03", "3333")
    item = [p for p in client.get("/api/student/me/practice", headers=S).json() if p["assignment_id"] == st["assignment_id"]][0]
    assert "answer" not in str(item["questions"]) and item["status"] == "not_started"  # no answer key before submitting
    body = {"answers": [{"question_id": q["id"], "choice": "B"} for q in item["questions"]]}
    first = client.post(f"/api/student/me/practice/{st['assignment_id']}", headers=S, json=body).json()
    again = client.post(f"/api/student/me/practice/{st['assignment_id']}", headers=S, json={"answers": [
        {"question_id": item["questions"][0]["id"], "choice": "A"}]}).json()
    assert first["status"] == "submitted" and again["already_submitted"] and again["result"] == first["result"]
    assert client.patch(f"/api/questions/{item['questions'][0]['id']}", headers=H, json={"stem": "x"}).json()["error"] == "already_assigned"
    st = client.get(f"/api/assessments/{a['id']}/practice", headers=H).json()
    assert [s["status"] for s in st["students"] if s["student"]["student_code"] == "7A-03"] == ["submitted"]

    ov = client.get("/api/classes/cl_7a/overview?subject=mathematics", headers=H).json()
    assert ov["class"]["name"] == "7A" and ov["student_count"] == 5 and ov["assessment_count"] >= 1
    assert all(h["id"] for h in ov["history"]) and "fractions" in ov["topics"]
    empty = client.get("/api/classes/cl_7a/overview?subject=biology", headers=H).json()
    assert empty["subject"] == "biology"


def test_other_teacher_cannot_reach_class_report_or_images(client):
    from app.db import SessionLocal
    from app.models import ClassRoom, Teacher
    from app.security import hash_secret
    db = SessionLocal()
    if not db.get(Teacher, "t_third"):
        db.add(Teacher(id="t_third", email="third@mindtrace.demo", name="Third", password_hash=hash_secret("pw999999")))
        db.add(ClassRoom(id="cl_9c", teacher_id="t_third", name="9C", grade="9"))
        db.commit()
    db.close()
    H3 = login(client, "third@mindtrace.demo", "pw999999")
    assert client.get("/api/classes/cl_7a/overview", headers=H3).status_code == 404
    assert client.get("/api/classes/cl_7a/overview?include_understanding=true", headers=H3).status_code == 404
    assert client.get("/api/classes/cl_7a/students", headers=H3).status_code == 404
    assert client.get("/api/students/st_01/report", headers=H3).status_code == 404
    rep = client.get("/api/students/st_01/report", headers=login(client)).json()
    assert rep["student"]["display_name"] == "Aarav" and rep["assessments"]
    img = next((x["image_url"] for x in rep["assessments"] if x["image_url"]), None)
    assert img and client.get(img, headers=H3).status_code == 403 and client.get(img, headers=login(client)).status_code == 200
    assert client.get("/api/media/scans/..%2Fsecret.txt", headers=H3).status_code == 404


def test_class_understanding_uses_only_confirmed_scored_answers(client, gem):
    H = login(client)
    assessment, pages, _ = _mixed(client, H)
    aid = assessment["id"]
    first, second, written = assessment["questions"]
    question_ids = [q["id"] for q in assessment["questions"]]
    wrong = next(choice for choice in first["options"] if choice != first["answer"])
    choices = [wrong, second["answer"]]
    for i, roll in enumerate(("01", "02")):
        gem["readings"].append(_reading(roll, question_ids, choices, "The forces balance."))
        scan = upload(client, H, aid, photo(pages[i], choices + [""], types=TYPES, seed=i)).json()
        if roll == "01":
            saved = review(client, H, scan["scan_id"], confirmed=True,
                           answers=[{"question_id": second["id"], "final": "blank"}]).json()
            assert saved["status"] == "accepted"

    url = "/api/classes/cl_7a/overview?subject=physics"
    assert "understanding" not in client.get(url, headers=H).json()
    url += "&include_understanding=true"
    data = client.get(url, headers=H).json()["understanding"]
    assert len(data["students"]) == 5 and {"student_code", "pin_hash"}.isdisjoint(data["students"][0])
    records = [r for r in data["results"] if r["assessment_id"] == aid]
    assert {r["student_id"] for r in records} == {"st_01"}
    assert sum(r["answered"] for r in records) == 2 and sum(r["correct"] for r in records) == 0
    concepts = {c["name"]: c for c in data["concepts"]}
    assert aid in concepts[written["concept"]]["assessment_ids"]
    mistakes = concepts[first["concept"]]["mistakes"]
    assert any(m["stem"] == first["stem"] and m["choice"] == first["options"][wrong] for m in mistakes)
    assert aid not in {r["assessment_id"] for r in client.get(url.replace("physics", "biology"), headers=H).json()["understanding"]["results"]}
    assert client.get(url, headers=_student(client, "7A-01", "1111")).status_code == 401


def test_expired_session_and_me(client, monkeypatch):
    H = login(client)
    assert client.get("/api/auth/me", headers=H).json()["teacher"]["id"] == "t_demo"
    S = _student(client, "7A-04", "4444")
    assert client.get("/api/auth/me", headers=S).json()["role"] == "student"
    monkeypatch.setattr(config, "SESSION_HOURS", 0)
    r = client.get("/api/classes", headers=H)
    assert r.status_code == 401 and r.json()["error"] == "session_expired"
    assert client.get("/api/student/me/results", headers=S).json()["error"] == "session_expired"
