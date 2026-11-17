"""Shared helpers for the scanning tests: a printed assessment, synthetic photos and fake Gemini readings."""
from tests import synth


def login(client, email="teacher@mindtrace.demo", password="demo1234"):
    r = client.post("/api/auth/teacher/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def printed(client, H, n=3):
    """Generate (samples), approve and print an assessment. Returns (id, question ids, rendered pages, pdf)."""
    a = client.post("/api/assessments/generate", headers=H, json={"class_id": "cl_7a", "topic": "fractions",
                                                                   "concepts_text": "adding", "num_questions": n}).json()
    assert client.post(f"/api/assessments/{a['id']}/approve", headers=H).json()["status"] == "approved"
    pdf = client.get(f"/api/assessments/{a['id']}/print", headers=H).content
    return a["id"], [q["id"] for q in a["questions"]], synth.render_pages(pdf), pdf


def reading(roll, marks, qids, legibility="clear", warnings=(), code="", page=(1, 1), cls="7A"):
    """A raw Gemini reply. marks per question: 'B' single, 'AB' multiple, '' blank, 'b' ambiguous, '?' unreadable."""
    answers = []
    for qid, m in zip(qids, marks):
        if m == "?":
            answers.append({"question_id": qid, "marked": [], "state": "unreadable"})
        elif m.islower():
            answers.append({"question_id": qid, "marked": [m.upper()], "state": "ambiguous", "note": "faint"})
        else:
            answers.append({"question_id": qid, "marked": list(m),
                            "state": {0: "blank", 1: "single"}.get(len(m), "multiple")})
    return {"roll_number": {"text": roll, "legibility": legibility}, "class_section": cls, "paper_code": code,
            "page": {"number": page[0], "of": page[1]}, "answers": answers, "warnings": list(warnings)}


def photo(page, marks, n=3, **kw):
    """Fill the bubbles on a rendered page the way a student would, then 'photograph' it."""
    ink = [m.upper() if m not in ("?",) else "" for m in marks]
    return synth.jpeg(synth.photograph(synth.fill(page, n, ink), **kw))


def upload(client, H, aid, jpg, roll_number=None, replace=False):
    data = {"roll_number": roll_number} if roll_number is not None else None
    return client.post(f"/api/assessments/{aid}/scans", headers=H, params={"replace": replace} if replace else None,
                       files={"image": ("paper.jpg", jpg, "image/jpeg")}, data=data)


def review(client, H, scan_id, **body):
    return client.patch(f"/api/scans/{scan_id}/review", headers=H, json=body)
