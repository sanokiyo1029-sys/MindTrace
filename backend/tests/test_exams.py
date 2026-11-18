from datetime import datetime, timedelta
from uuid import uuid4

from app.routes import exams
from app.seed import APK_TESTER_EMAIL, APK_TESTER_PASSWORD
from tests.scanhelp import login


def student(client, code, pin):
    r = client.post("/api/auth/student/login", json={"student_code": code, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def draft(client, headers):
    r = client.post("/api/assessments/generate", headers=headers, json={
        "class_id": "cl_7a", "topic": "fractions", "concepts_text": "Adding fractions", "num_questions": 1,
    })
    assert r.status_code == 200, r.text
    return r.json()


def publish(client, headers, aid, minutes=10):
    return client.post("/api/exams", headers=headers, json={"assessment_id": aid, "duration_minutes": minutes})


def test_online_exam_flow_and_privacy(client):
    teacher = login(client)
    learner = student(client, "7A-01", "1111")
    peer = student(client, "7A-02", "2222")
    stranger = student(client, "7T-01", "1212")
    unrelated_teacher = login(client, APK_TESTER_EMAIL, APK_TESTER_PASSWORD)
    assessment = draft(client, teacher)
    aid = assessment["id"]
    assert publish(client, teacher, aid).status_code == 409
    for q in (
        {"type": "multi_select", "stem": "Pick two equivalent fractions.", "marks": 2,
         "options": {"A": "1/2", "B": "2/4", "C": "1/3"}, "answers": ["A", "B"]},
        {"type": "match", "stem": "Match the amounts.", "marks": 2, "pairs": [["1/2", "50%"], ["1/4", "25%"]]},
        {"type": "numerical", "stem": "Give a numerical result.", "marks": 2, "value": "0.5", "tolerance": "0.01"},
        {"type": "short", "stem": "Explain your reasoning.", "marks": 3, "model_answer": "Secret model answer"},
    ):
        added = client.post(f"/api/assessments/{aid}/questions", headers=teacher, json=q)
        assert added.status_code == 200, added.text
    approved = client.post(f"/api/assessments/{aid}/approve", headers=teacher)
    assert approved.status_code == 200, approved.text
    questions = approved.json()["questions"]
    assert publish(client, teacher, aid, minutes=0).status_code == 422
    assert publish(client, unrelated_teacher, aid).status_code == 403
    assert publish(client, teacher, aid).json()["question_count"] == 5
    assert publish(client, teacher, aid).status_code == 200
    assert publish(client, teacher, aid, minutes=11).status_code == 409
    assert aid in [item["id"] for item in client.get("/api/exams", headers=teacher).json()]
    assert aid not in [item["id"] for item in client.get("/api/exams", headers=unrelated_teacher).json()]
    assert client.get(f"/api/assessments/{aid}/print", headers=teacher).status_code == 409
    assert client.post(f"/api/assessments/{aid}/assign", headers=teacher).status_code == 409
    assert client.patch(f"/api/questions/{questions[0]['id']}", headers=teacher, json={"stem": "Changed"}).status_code == 409
    assert client.get(f"/api/exams/{aid}", headers=learner).status_code == 401
    path = f"/api/student/me/exams/{aid}"
    assert client.get(path, headers=stranger).status_code == 404
    assert client.post(path + "/start", headers=stranger).status_code == 404
    assert client.put(path + "/attempt", headers=learner, json={"answers": {}, "version": 1}).status_code == 409
    assert next(e for e in client.get("/api/student/me/exams", headers=learner).json() if e["id"] == aid)["status"] == "ready"
    assert "questions" not in client.get(path, headers=learner).json()

    started = client.post(path + "/start", headers=learner).json()
    attempt = started["attempt"]
    assert client.post(path + "/start", headers=learner).json()["attempt"]["deadline_at"] == attempt["deadline_at"]
    assert client.get(path, headers=peer).json()["attempt"]["status"] == "ready"
    assert all(not {"answer", "answers", "pairs", "value", "accepted", "model_answer"} & public.keys() for public in started["questions"])
    one, multi, match, number, short = [q["id"] for q in questions]
    matching = started["questions"][2]
    letter = next(k for k, value in matching["right"].items() if value == "50%")
    answers = {one: questions[0]["answer"], multi: ["A"], match: {"1": letter}, number: "1/2", short: "My own reasoning"}
    report_path = f"/api/exams/{aid}"
    grade_path = f"{report_path}/attempts/{attempt['id']}"
    assert client.get(report_path, headers=unrelated_teacher).status_code == 403
    assert client.patch(grade_path, headers=teacher, json={"version": 1, "scores": {}}).status_code == 409
    assert client.put(path + "/attempt", headers=learner, json={"version": 1, "answers": {multi: "A"}}).status_code == 400
    saved = client.put(path + "/attempt", headers=learner, json={"version": 1, "answers": answers}).json()
    assert saved["attempt"]["answers"] == answers
    assert client.put(path + "/attempt", headers=learner, json={"version": 1, "answers": {}}).status_code == 409
    submitted = client.put(path + "/attempt", headers=learner, json={
        "version": saved["attempt"]["version"], "answers": answers, "submit": True,
    }).json()
    assert submitted["attempt"]["status"] == "submitted"
    assert "score" not in submitted["attempt"] and "answers" not in submitted["attempt"]
    assert client.put(path + "/attempt", headers=learner, json={"version": 1, "answers": {}}).json()["attempt"]["status"] == "submitted"
    report = client.get(report_path, headers=teacher).json()
    result = next(row["attempt"] for row in report["students"] if row["attempt"].get("id") == attempt["id"])
    assert result["answers"] == answers and result["to_mark"] == 1
    assert result["scores"][multi] == 1 and result["scores"][match] == 1 and result["scores"][number] == 2
    assert client.patch(grade_path, headers=teacher, json={"version": result["version"], "scores": {}, "release": True}).status_code == 409
    assert client.patch(grade_path, headers=teacher, json={"version": result["version"], "scores": {short: 4}}).status_code == 400
    released = client.patch(grade_path, headers=teacher, json={
        "version": result["version"], "scores": {short: 2.5}, "release": True,
    }).json()
    result = client.get(path, headers=learner).json()
    assert result["attempt"]["status"] == "released" and result["attempt"]["score"] == released["score"] == 7.5
    assert result["attempt"]["scores"][short] == 2.5 and result["attempt"]["answers"] == answers
    assert "Secret model answer" not in str(result)


def test_deadline_preserves_last_saved_answers_and_never_extends(client, monkeypatch):
    teacher, learner = login(client), student(client, "7A-03", "3333")
    draft_exam = draft(client, teacher)
    aid, q = draft_exam["id"], draft_exam["questions"][0]
    assert client.post(f"/api/assessments/{aid}/approve", headers=teacher).status_code == 200
    assert publish(client, teacher, aid, minutes=1).status_code == 200
    path = f"/api/student/me/exams/{aid}"
    started = client.post(path + "/start", headers=learner).json()["attempt"]
    answer = {q["id"]: q["answer"]}
    write_id = str(uuid4())
    draft_save = {"version": 1, "answers": answer, "write_id": write_id}
    saved = client.put(path + "/attempt", headers=learner, json=draft_save).json()
    assert saved["attempt"]["version"] == 2 and saved["attempt"]["last_write_id"] == write_id
    replay = client.put(path + "/attempt", headers=learner, json=draft_save).json()
    assert replay["attempt"]["version"] == 2 and replay["attempt"]["answers"] == answer
    deadline = datetime.fromisoformat(started["deadline_at"])
    monkeypatch.setattr(exams, "now", lambda: deadline + timedelta(seconds=1))
    late = client.put(path + "/attempt", headers=learner, json={
        "version": 2, "answers": {}, "submit": True, "write_id": str(uuid4()),
    }).json()
    assert late["attempt"]["status"] == "submitted" and late["attempt"]["submission_reason"] == "deadline"
    assert late["attempt"]["last_write_id"] == write_id
    assert client.post(path + "/start", headers=learner).json()["attempt"]["id"] == started["id"]
    report = client.get(f"/api/exams/{aid}", headers=teacher).json()
    assert next(row["attempt"] for row in report["students"] if row["attempt"].get("id") == started["id"])["answers"] == answer
