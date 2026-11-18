"""'Continue with Google': sign-in, signup, workspace isolation and logout.
Google's token check is replaced by a fake; the real one runs google-auth against Google's keys."""
import pytest

from app import config
from app.routes import auth

CLIENT = "web-client.apps.googleusercontent.com"


def test_off_until_configured(client):
    assert client.get("/api/auth/config").json() == {"google_client_id": None}
    assert client.post("/api/auth/google", json={"credential": "x"}).json()["error"] == "google_not_configured"


@pytest.fixture
def google(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_IDS", [CLIENT])
    monkeypatch.setattr(config, "GOOGLE_TEACHER_EMAILS", {"rohan@example.com"})
    claims = {"sub": "google-old-teacher", "hd": "example.com"}

    def fake_verify(credential):
        if credential == "expired":
            raise ValueError("Token expired")
        return dict(claims)

    monkeypatch.setattr(auth, "_verify_google", fake_verify)
    return claims


def test_linked_account_gets_teacher_access_only_and_logout_ends_it(client, google):
    assert client.get("/api/auth/config").json()["google_client_id"] == CLIENT
    google.update(email="Rohan@Example.com", email_verified=True)
    r = client.post("/api/auth/google", json={"credential": "ok"})
    assert r.status_code == 200 and r.json()["teacher"]["email"] == "teacher@mindtrace.demo"
    H = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/assessments", headers=H).status_code == 200
    assert client.get("/api/student/me/results", headers=H).status_code == 401  # never a student
    assert client.post("/api/auth/logout", headers=H).json() == {"ok": True}
    assert client.get("/api/assessments", headers=H).status_code == 401


def test_teacher_whose_email_matches_is_linked(client, google):
    google.update(email="teacher@mindtrace.demo", email_verified=True, hd="mindtrace.demo")
    assert client.post("/api/auth/google", json={"credential": "ok"}).status_code == 200


@pytest.mark.parametrize("claims,credential,status,error", [
    ({"email": "stranger@example.com", "email_verified": True}, "ok", 403, "google_not_linked"),
    ({"email": "rohan@example.com", "email_verified": False}, "ok", 403, "google_email_unverified"),
    ({}, "expired", 401, "bad_google_token"),
])
def test_unlinked_unverified_and_bad_tokens_rejected(client, google, claims, credential, status, error):
    google.update(claims)
    r = client.post("/api/auth/google", json={"credential": credential})
    assert r.status_code == status and r.json()["error"] == error


def test_signup_creates_an_isolated_teacher_and_returns_to_it_by_google_id(client, google):
    google.update(sub="new-google-teacher", name="Sample teacher", email="new-mindtrace-teacher@gmail.com", email_verified=True)
    r = client.post("/api/auth/google", json={"credential": "ok", "allow_signup": True})
    assert r.status_code == 200
    first = r.json()
    headers = {"Authorization": f"Bearer {first['token']}"}
    assert first["teacher"]["id"] != "t_demo"
    assert client.get("/api/classes", headers=headers).json() == []
    assert client.get("/api/classes/cl_7a/overview", headers=headers).status_code == 404
    assert client.get("/api/student/me/results", headers=headers).status_code == 401

    google.update(sub="different-google-user")
    assert client.post("/api/auth/google", json={"credential": "ok", "allow_signup": True}).status_code == 409
    google.update(sub="new-google-teacher", email="changed-mindtrace-teacher@gmail.com")
    repeat = client.post("/api/auth/google", json={"credential": "ok"}).json()
    assert repeat["teacher"]["id"] == first["teacher"]["id"]


def test_signup_cannot_claim_existing_teacher_with_unmanaged_email(client, google):
    google.pop("hd")
    google.update(email="teacher@mindtrace.demo", email_verified=True)
    response = client.post("/api/auth/google", json={"credential": "ok", "allow_signup": True})
    assert response.status_code == 403 and response.json()["error"] == "google_not_linked"


def test_student_google_requires_pin_then_signs_in_to_the_same_student(client, google):
    google.update(sub="student-google-id", email="student-fixture@gmail.com", email_verified=True)
    body = {"credential": "ok", "role": "student"}
    assert client.post("/api/auth/google", json=body).json()["error"] == "google_student_link_required"
    link = {**body, "student_link": {"student_code": "7A-04", "pin": "0000"}}
    assert client.post("/api/auth/google", json=link).status_code == 401
    link["student_link"]["pin"] = "4444"
    linked = client.post("/api/auth/google", json=link)
    assert linked.status_code == 200 and linked.json()["student"]["id"] == "st_04"
    repeat = client.post("/api/auth/google", json=body).json()
    assert repeat["student"]["id"] == "st_04"
    headers = {"Authorization": f"Bearer {repeat['token']}"}
    assert client.get("/api/student/me/results", headers=headers).status_code == 200
    assert client.get("/api/classes", headers=headers).status_code == 401
    link["student_link"] = {"student_code": "7A-05", "pin": "5555"}
    assert client.post("/api/auth/google", json=link).status_code == 409
    google.update(sub="another-google-id")
    link["student_link"] = {"student_code": "7A-04", "pin": "4444"}
    assert client.post("/api/auth/google", json=link).status_code == 409
