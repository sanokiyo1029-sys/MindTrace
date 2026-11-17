"""'Continue with Google': linked teachers only, student access never granted, logout ends the session.
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
    claims = {}

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
    google.update(email="teacher@mindtrace.demo", email_verified=True)
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
