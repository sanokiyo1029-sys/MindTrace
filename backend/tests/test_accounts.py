"""Phase 1 accounts: class join codes, student self-registration in several classes, email/password + code/PIN
logins, login throttling, password recovery, profiles and teacher roster management. All names are fictional."""
import pytest

from app import mailer
from app.db import SessionLocal
from app.models import ClassRoom, Teacher
from app.security import hash_secret
from tests import synth
from tests.scanhelp import login, photo, upload

CLS = "cl_acc"  # its own class, so other tests keep their 5-student class 7A


@pytest.fixture(scope="module", autouse=True)
def account_class():
    from app.models import Student
    with SessionLocal() as db:
        if not db.get(ClassRoom, CLS):
            db.add(ClassRoom(id=CLS, teacher_id="t_demo", name="8Z", grade="8"))
            db.add(Student(id="st_8z_01", class_id=CLS, display_name="Ola", student_code="8Z-01", roll_no="01",
                           pin_hash=hash_secret("1234")))
            db.add(Student(id="st_8z_02", class_id=CLS, display_name="Pia", student_code="8Z-02", roll_no="02",
                           pin_hash=hash_secret("2345")))
            db.commit()


def printed_for(client, H):
    a = client.post("/api/assessments/generate", headers=H, json={"class_id": CLS, "num_questions": 3}).json()
    client.post(f"/api/assessments/{a['id']}/approve", headers=H)
    pdf = client.get(f"/api/assessments/{a['id']}/print", headers=H).content
    return a["id"], synth.render_pages(pdf)


def _H(r):
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _code(client, H, class_id=CLS):
    return next(c for c in client.get("/api/classes", headers=H).json() if c["id"] == class_id)["join_code"]


def _signup(client, code, **kw):
    body = {"name": "Ira Sen", "email": "ira.sen@example.com", "password": "orbit2026", "class_code": code,
            "roll_no": "31"} | kw
    return client.post("/api/auth/student/signup", json=body)


@pytest.fixture(scope="module")
def second_teacher():
    with SessionLocal() as db:
        if not db.get(Teacher, "t_phase1"):
            db.add(Teacher(id="t_phase1", email="phase1@example.com", name="Ms Phase", password_hash=hash_secret("phase1pass")))
            db.add(ClassRoom(id="cl_9p", teacher_id="t_phase1", name="9P", grade="9"))
            db.commit()
    return "phase1@example.com", "phase1pass"


def test_student_signs_up_with_class_code_and_joins_a_second_class(client, second_teacher):
    T = login(client)
    code = _code(client, T)
    assert len(code) == 7 and code[3] == "-"
    assert _signup(client, "NOPE-00").json()["error"] == "bad_class_code"
    assert _signup(client, code, roll_no="01").json()["error"] == "roll_taken"       # Ola is roll 01 in 8Z
    assert _signup(client, code, email="teacher@mindtrace.demo").json()["error"] == "email_taken"
    assert _signup(client, code, password="short").json()["error"] == "weak_password"
    S = _H(_signup(client, code))
    assert [c["name"] for c in client.get("/api/student/classes", headers=S).json()] == ["8Z"]
    assert client.get("/api/student/me/results", headers=S).json() == {"student": {"display_name": "Ira Sen"}, "assessments": []}
    # the teacher sees the new student on the roster, roll 31, with an account
    roster = client.get(f"/api/classes/{CLS}/students", headers=T).json()
    assert any(s["roll_no"] == "31" and s["has_account"] for s in roster)

    T2 = login(client, *second_teacher)
    S_again = _H(client.post("/api/auth/student/login", json={"email": "IRA.SEN@example.com", "password": "orbit2026"}))
    joined = client.post("/api/student/classes/join", headers=S_again, json={"class_code": _code(client, T2, "cl_9p"),
                                                                             "roll_no": "4"}).json()
    assert sorted(c["name"] for c in joined) == ["8Z", "9P"]
    assert client.post("/api/student/classes/join", headers=S_again,
                       json={"class_code": code, "roll_no": "77"}).json()["error"] == "already_joined"
    # an old-style code + PIN student can't join more classes (no account), but still logs in as before
    old = _H(client.post("/api/auth/student/login", json={"student_code": "8Z-02", "pin": "2345"}))
    assert client.post("/api/student/classes/join", headers=old,
                       json={"class_code": code, "roll_no": "88"}).json()["error"] == "account_required"
    # the teacher can replace the code; the old one stops working
    new = client.post(f"/api/classes/{CLS}/join-code", headers=T).json()["join_code"]
    assert new != code and _signup(client, code, email="x@example.com").json()["error"] == "bad_class_code"


def test_account_sees_results_from_its_class_and_nobody_else_does(client):
    T = login(client)
    S = _H(_signup(client, _code(client, T), email="kai.rao@example.com", name="Kai Rao", roll_no="32"))
    aid, pages = printed_for(client, T)  # sheets include the new student
    sc = upload(client, T, aid, photo(pages[0], ["A", "B", "B"]), roll_number="32").json()  # AI off: bubble reader
    assert sc["student"]["display_name"] == "Kai Rao"
    assert client.patch(f"/api/scans/{sc['scan_id']}/review", headers=T, json={"confirmed": True}).json()["status"] == "accepted"
    assert client.post(f"/api/assessments/{aid}/confirm", headers=T).status_code == 200
    mine = client.get("/api/student/me/results", headers=S).json()["assessments"]
    row = next(a for a in mine if a["assessment_id"] == aid)
    assert row["status"] == "released" and client.get(row["scan_url"], headers=S).status_code == 200
    other = _H(_signup(client, _code(client, T), email="lee.m@example.com", name="Lee M", roll_no="33"))
    assert client.get(row["scan_url"], headers=other).status_code == 403
    assert not [a for a in client.get("/api/student/me/results", headers=other).json()["assessments"]
                if a.get("scan_url") == row["scan_url"]]


def test_login_throttling(client):
    for _ in range(5):
        assert client.post("/api/auth/student/login", json={"student_code": "8Z-01", "pin": "0000"}).status_code == 401
    r = client.post("/api/auth/student/login", json={"student_code": "8Z-01", "pin": "1234"})
    assert r.status_code == 429 and r.json()["error"] == "too_many_attempts"  # even the right PIN waits


def test_password_recovery(client, monkeypatch):
    T = login(client)
    _H(_signup(client, _code(client, T), email="mia.k@example.com", name="Mia K", roll_no="34"))
    # no email set up: same answer for any address, and nothing is created
    r = client.post("/api/auth/password/forgot", json={"email": "mia.k@example.com"}).json()
    assert r == {"ok": True, "email_enabled": False}
    sent = []
    monkeypatch.setattr(mailer, "enabled", lambda: True)
    monkeypatch.setattr(mailer, "send", lambda to, subject, body: sent.append((to, body)) or True)
    assert client.post("/api/auth/password/forgot", json={"email": "nobody@example.com"}).json()["ok"]
    assert not sent  # unknown email: no mail, same reply
    old = _H(client.post("/api/auth/student/login", json={"email": "mia.k@example.com", "password": "orbit2026"}))
    client.post("/api/auth/password/forgot", json={"email": "Mia.K@example.com"})
    (to, body), = sent
    token = body.split("#token=")[1].split()[0]
    assert to == "mia.k@example.com"
    assert client.post("/api/auth/password/reset", json={"token": token, "password": "weak"}).json()["error"] == "weak_password"
    assert client.post("/api/auth/password/reset", json={"token": token, "password": "newplanet9"}).json()["ok"]
    assert client.post("/api/auth/password/reset", json={"token": token, "password": "again12345"}).json()["error"] == "bad_reset_link"
    assert client.get("/api/student/classes", headers=old).status_code == 401  # signed out everywhere
    assert client.post("/api/auth/student/login", json={"email": "mia.k@example.com", "password": "newplanet9"}).status_code == 200
    # teacher reset works the same way
    sent.clear()
    client.post("/api/auth/password/forgot", json={"email": "teacher@mindtrace.demo"})
    assert sent and sent[0][0] == "teacher@mindtrace.demo"


def test_admin_reset_link(client):
    from app.admin import reset_link
    link = reset_link("teacher@mindtrace.demo")
    assert "/reset-password#token=" in link


def test_profile(client):
    T = login(client)
    S = _H(_signup(client, _code(client, T), email="noor.a@example.com", name="Noor A", roll_no="35"))
    assert client.get("/api/auth/profile", headers=S).json()["email"] == "noor.a@example.com"
    p = client.patch("/api/auth/profile", headers=S, json={"name": "Noor Ahmed"}).json()
    assert p["name"] == "Noor Ahmed"
    assert any(s["display_name"] == "Noor Ahmed" for s in client.get(f"/api/classes/{CLS}/students", headers=T).json())
    assert client.patch("/api/auth/profile", headers=S, json={"email": "n@example.com"}).json()["error"] == "wrong_password"
    other = _H(client.post("/api/auth/student/login", json={"email": "noor.a@example.com", "password": "orbit2026"}))
    p = client.patch("/api/auth/profile", headers=S, json={"current_password": "orbit2026", "new_password": "comet2027x",
                                                           "email": "noor.ahmed@example.com"}).json()
    assert p["email"] == "noor.ahmed@example.com"
    assert client.get("/api/auth/profile", headers=other).status_code == 401   # other session ended
    assert client.get("/api/auth/profile", headers=S).status_code == 200       # this one kept
    old_style = _H(client.post("/api/auth/student/login", json={"student_code": "8Z-02", "pin": "2345"}))
    assert client.patch("/api/auth/profile", headers=old_style, json={"new_password": "x"}).json()["error"] == "account_required"
    assert client.get("/api/auth/profile", headers=T).json()["role"] == "teacher"


def test_teacher_roster_management(client, second_teacher):
    T = login(client)
    added = client.post(f"/api/classes/{CLS}/students", headers=T, json={"display_name": "Zed Q", "roll_no": "36"}).json()
    assert added["student_code"] == "8Z-36" and len(added["pin"]) == 4
    S = _H(client.post("/api/auth/student/login", json={"student_code": "8Z-36", "pin": added["pin"]}))
    assert client.post(f"/api/classes/{CLS}/students", headers=T, json={"display_name": "Dup", "roll_no": "36"}).json()["error"] == "roll_taken"
    reset = client.post(f"/api/classes/{CLS}/students/{added['id']}/reset", headers=T).json()
    assert reset["pin"] and reset["temporary_password"] is None
    assert client.get("/api/student/classes", headers=S).status_code == 401  # old session ended
    assert client.post("/api/auth/student/login", json={"student_code": "8Z-36", "pin": reset["pin"]}).status_code == 200
    T2 = login(client, *second_teacher)
    assert client.post(f"/api/classes/{CLS}/students/{added['id']}/reset", headers=T2).status_code == 404
    assert client.delete(f"/api/classes/{CLS}/students/{added['id']}", headers=T2).status_code == 404
    assert client.delete(f"/api/classes/{CLS}/students/{added['id']}", headers=T).json()["ok"]
    # a student with papers (Ola, roll 01) is never removed
    printed_for(client, T)
    assert client.delete(f"/api/classes/{CLS}/students/st_8z_01", headers=T).json()["error"] == "has_papers"
