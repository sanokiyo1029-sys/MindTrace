"""The APK test teacher signs in with a password, sees only its own class 7T, and can't touch demo class 7A."""
from app.seed import APK_TESTER_EMAIL, APK_TESTER_PASSWORD
from tests.scanhelp import login


def test_apk_tester_has_its_own_class_only(client):
    H = login(client, APK_TESTER_EMAIL, APK_TESTER_PASSWORD)
    assert [c["id"] for c in client.get("/api/classes", headers=H).json()] == ["cl_7t"]
    roster = client.get("/api/classes/cl_7t/students", headers=H).json()
    assert [s["roll_no"] for s in roster] == ["01", "02", "03", "04", "05"]
    assert client.get("/api/classes/cl_7a/students", headers=H).status_code == 404
    a = client.post("/api/assessments/generate", headers=H, json={"class_id": "cl_7t", "topic": "fractions",
                                                                   "concepts_text": "adding", "num_questions": 3})
    assert a.status_code == 200 and a.json()["class_id"] == "cl_7t"
    assert client.post("/api/assessments/generate", headers=H, json={"class_id": "cl_7a", "topic": "fractions",
                                                                     "concepts_text": "x", "num_questions": 1}).status_code == 404
    demo = login(client)
    assert a.json()["id"] not in {x["id"] for x in client.get("/api/assessments", headers=demo).json()}
