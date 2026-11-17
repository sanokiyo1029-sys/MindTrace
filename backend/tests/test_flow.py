"""Full teacher loop on synthetic phone photos: generate -> approve -> print -> scan -> review -> insights -> follow-up."""
from tests import synth


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


def test_full_loop(client):
    H = _login(client)
    # 1. generate + edit + approve
    r = client.post("/api/assessments/generate", headers=H,
                    json={"class_id": "cl_7a", "topic": "fractions", "concepts_text": "adding fractions", "num_questions": 3})
    assert r.status_code == 200, r.text
    a = r.json()
    aid, qs = a["id"], a["questions"]
    assert len(qs) == 3 and all(q["validation_errors"] == [] for q in qs)

    # can't print a draft
    assert client.get(f"/api/assessments/{aid}/print", headers=H).status_code == 409
    # a wrong answer key is caught by the validator and blocks approval
    bad = client.patch(f"/api/questions/{qs[0]['id']}", headers=H, json={"answer": "A"}).json()
    assert any("Answer key looks wrong" in e for e in bad["validation_errors"])
    assert client.post(f"/api/assessments/{aid}/approve", headers=H).status_code == 400
    client.patch(f"/api/questions/{qs[0]['id']}", headers=H, json={"answer": "B"})
    assert client.post(f"/api/assessments/{aid}/approve", headers=H).json()["status"] == "approved"

    # 2. print
    r = client.get(f"/api/assessments/{aid}/print", headers=H)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    pages = synth.render_pages(r.content)
    assert len(pages) == 5

    # 3. scan 5 "photos". Q1 wrong pattern: 3 of 5 pick A (2/6)
    marks = [["A", "B", "B"], ["A", "A", "A"], ["A", "B", "C"], ["B", "B", "B"], ["AB", "B", "B"]]
    results = []
    for i, (page, m) in enumerate(zip(pages, marks)):
        photo = synth.photograph(synth.fill(page, 3, m), angle=(-1) ** i * (3 + i), seed=i)
        r = client.post(f"/api/assessments/{aid}/scans", headers=H,
                        files={"image": (f"p{i}.jpg", synth.jpeg(photo), "image/jpeg")})
        assert r.status_code == 200, r.text
        results.append(r.json())
    assert [x["status"] for x in results] == ["accepted"] * 4 + ["needs_review"]
    assert results[0]["answers"][0]["detected"] == "A" and results[3]["answers"][0]["detected"] == "B"
    assert results[4]["answers"][0]["state"] == "multiple"
    assert len({x["sheet_id"] for x in results}) == 5

    # duplicate scan doesn't change counts
    dup = client.post(f"/api/assessments/{aid}/scans", headers=H,
                      files={"image": ("d.jpg", synth.jpeg(synth.photograph(synth.fill(pages[0], 3, marks[0]))), "image/jpeg")}).json()
    assert dup["status"] == "duplicate"
    prog = client.get(f"/api/assessments/{aid}/scans", headers=H).json()
    assert (prog["total"], prog["accepted"], prog["needs_review"], prog["remaining"]) == (5, 4, 1, 0)

    # garbage photo is rejected with a reason, never guessed
    import numpy as np
    junk = client.post(f"/api/assessments/{aid}/scans", headers=H,
                       files={"image": ("j.jpg", synth.jpeg(np.full((600, 400, 3), 128, np.uint8)), "image/jpeg")}).json()
    assert junk["status"] == "rejected" and junk["reject_reason"]

    # 4. insights blocked until review is done
    assert client.get(f"/api/assessments/{aid}/insights", headers=H).status_code == 409
    rv = client.patch(f"/api/scans/{results[4]['scan_id']}/review", headers=H,
                      json={"answers": [{"question_id": qs[0]["id"], "final": "A"}], "confirmed": True}).json()
    assert rv["status"] == "accepted"
    assert client.post(f"/api/assessments/{aid}/confirm", headers=H).json()["status"] == "confirmed"

    ins = client.get(f"/api/assessments/{aid}/insights", headers=H).json()
    assert ins["papers"]["verified"] == 5
    q1 = ins["questions"][0]
    assert q1["distribution"]["A"] == 4 and q1["correct"] == 1
    top = ins["misconceptions"][0]
    assert top["misconception_id"] == "M_ADD_DENOMS" and top["status"] == "possible"
    assert top["students_affected"] == 4 and top["teaching_action"]["steps"] and top["followup_question"]
    assert "Aarav" not in str(ins)  # no names in the class report

    # 5. follow-up quiz
    f = client.post(f"/api/assessments/{aid}/followup", headers=H, json={}).json()
    assert f["parent_assessment_id"] == aid and f["questions"] and f["status"] == "draft"
    assert all(q["validation_errors"] == [] for q in f["questions"])

    # 6. student sees only their own results
    s = client.post("/api/auth/student/login", json={"student_code": "7A-01", "pin": "1111"}).json()
    SH = {"Authorization": f"Bearer {s['token']}"}
    me = client.get("/api/student/me/results", headers=SH).json()
    assert me["student"]["display_name"] == "Aarav"
    assert len(me["assessments"]) == 1 and me["assessments"][0]["answers"][0]["chosen"] == "A"
    assert me["assessments"][0]["answers"][0]["maybe"]
    # student token can't reach teacher endpoints
    assert client.get(f"/api/assessments/{aid}/insights", headers=SH).status_code == 401
