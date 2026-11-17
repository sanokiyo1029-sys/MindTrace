"""Full teacher loop on synthetic phone photos, Gemini readings faked:
generate -> approve -> print (roll-number band, no QR) -> scan -> teacher review -> confirm -> scores -> insights.
"""
import pypdfium2 as pdfium

from tests.scanhelp import photo, printed, reading, review, upload


def _login(client):
    r = client.post("/api/auth/teacher/login", json={"email": "teacher@mindtrace.demo", "password": "demo1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_docs_authorize_and_query_token(client):
    # /docs gets an Authorize button; ?token= still works for links the browser opens directly
    assert "HTTPBearer" in client.get("/openapi.json").json()["components"]["securitySchemes"]
    tok = _login(client)["Authorization"][7:]
    assert client.get(f"/api/classes?token={tok}").status_code == 200
    assert client.get("/api/classes", headers={"Authorization": "Basic x"}).status_code == 401


def test_full_loop(client, gem):
    H = _login(client)
    # 1. generate + edit + approve: the validator still guards the answer key
    a = client.post("/api/assessments/generate", headers=H, json={"class_id": "cl_7a", "topic": "fractions",
                                                                   "concepts_text": "adding", "num_questions": 3}).json()
    q0 = a["questions"][0]["id"]
    assert client.get(f"/api/assessments/{a['id']}/print", headers=H).status_code == 409  # can't print a draft
    bad = client.patch(f"/api/questions/{q0}", headers=H, json={"answer": "A"}).json()
    assert any("Answer key looks wrong" in e for e in bad["validation_errors"])
    assert client.post(f"/api/assessments/{a['id']}/approve", headers=H).status_code == 400
    client.patch(f"/api/questions/{q0}", headers=H, json={"answer": "B"})

    # 2. print: one identical copy per student, roll-number band at the top, no QR / images, no names
    aid, qids, pages, pdf = printed(client, H)
    assert len(pages) == 5
    first = pdfium.PdfDocument(pdf)[0]
    text = first.get_textpage().get_text_range()
    assert "ROLL NO." in text and "CLASS / SECTION" in text and "Page 1 of 1" in text and "Aarav" not in text
    assert not any(o.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE for o in first.get_objects())

    # 3. scan 5 papers. Gemini reads the roll number; one paper is upside down, one roll is written "3" (roster "03"),
    #    Rehan double-marked Q1
    marks = [["A", "B", "B"], ["A", "A", "A"], ["A", "B", "C"], ["B", "B", "B"], ["AB", "B", "B"]]
    written = ["01", "02", "3", "04", "05"]
    out = []
    for i, (page, m, roll) in enumerate(zip(pages, marks, written)):
        gem["readings"].append(reading(roll, m, qids))
        r = upload(client, H, aid, photo(page, m, angle=(-1) ** i * (3 + i), seed=i, upside_down=(i == 3)))
        assert r.status_code == 200, r.text
        out.append(r.json())
    assert [x["status"] for x in out] == ["needs_review"] * 5  # Gemini results always get a teacher check
    assert [x["student"]["display_name"] for x in out] == ["Aarav", "Diya", "Kabir", "Meera", "Rehan"]
    assert {x["extracted_by"] for x in out} == {"gemini"}
    assert any(w["code"] == "roll_loose_match" for w in out[2]["warnings"])
    assert all(x["state"] == "single" for x in out[3]["answers"])  # upside-down photo: bubble reader agrees
    assert out[4]["answers"][0]["state"] == "multiple" and out[4]["answers"][0]["final"] is None
    assert "Aarav" not in str(gem["calls"]) and qids[0] in gem["calls"][0]["prompt"]  # no roster sent to Gemini
    prog = client.get(f"/api/assessments/{aid}/scans", headers=H).json()
    assert (prog["total"], prog["accepted"], prog["needs_review"]) == (5, 0, 5)

    # 4. teacher confirms; the double mark needs a decision first
    for x in out[:4]:
        assert review(client, H, x["scan_id"], confirmed=True).json()["status"] == "accepted"
    assert review(client, H, out[4]["scan_id"], confirmed=True).json()["error"] == "incomplete"
    assert review(client, H, out[4]["scan_id"], answers=[{"question_id": qids[0], "final": "A"}],
                  confirmed=True).json()["status"] == "accepted"

    # 5. the same paper again: no double counting until the teacher explicitly replaces it
    gem["readings"].append(reading("01", marks[0], qids))
    dup = upload(client, H, aid, photo(pages[0], marks[0], seed=9)).json()
    assert dup["status"] == "duplicate" and dup["duplicate_of"] == out[0]["scan_id"]
    prog = client.get(f"/api/assessments/{aid}/scans", headers=H).json()
    assert (prog["accepted"], prog["needs_review"]) == (5, 0) and prog["duplicates"][0]["scan_id"] == dup["scan_id"]
    assert review(client, H, dup["scan_id"], confirmed=True).json()["error"] == "already_confirmed"
    assert review(client, H, dup["scan_id"], replace=True, confirmed=True).json()["status"] == "accepted"
    prog = client.get(f"/api/assessments/{aid}/scans", headers=H).json()
    assert prog["accepted"] == 5 and out[0]["scan_id"] not in {s["scan_id"] for s in prog["scans"]}

    # 6. confirm -> insights; scores come from the confirmed answers and the approved key, deterministically
    assert client.post(f"/api/assessments/{aid}/confirm", headers=H).json()["status"] == "confirmed"
    ins = client.get(f"/api/assessments/{aid}/insights", headers=H).json()
    assert ins["papers"]["verified"] == 5
    assert ins["questions"][0]["distribution"]["A"] == 4 and ins["questions"][0]["correct"] == 1
    top = ins["misconceptions"][0]
    assert top["misconception_id"] == "M_ADD_DENOMS" and top["status"] == "possible" and top["students_affected"] == 4
    assert top["teaching_action"]["steps"] and top["followup_question"]
    assert "Aarav" not in str(ins)  # no names in the class report
    res = client.get(f"/api/assessments/{aid}/results", headers=H).json()
    assert {r["roll_no"]: (r["scan_status"], r["correct"]) for r in res} == {
        "01": ("accepted", 2), "02": ("accepted", 0), "03": ("accepted", 1), "04": ("accepted", 3), "05": ("accepted", 2)}

    # 7. follow-up quiz
    f = client.post(f"/api/assessments/{aid}/followup", headers=H, json={}).json()
    assert f["parent_assessment_id"] == aid and f["questions"] and f["status"] == "draft"

    # 8. student sees only their own results
    s = client.post("/api/auth/student/login", json={"student_code": "7A-01", "pin": "1111"}).json()
    SH = {"Authorization": f"Bearer {s['token']}"}
    me = client.get("/api/student/me/results", headers=SH).json()
    assert me["student"]["display_name"] == "Aarav"
    mine = [x for x in me["assessments"] if x["assessment_id"] == aid][0]
    assert [x["chosen"] for x in mine["answers"]] == ["A", "B", "B"] and mine["answers"][0]["maybe"]
    assert client.get(f"/api/assessments/{aid}/insights", headers=SH).status_code == 401
