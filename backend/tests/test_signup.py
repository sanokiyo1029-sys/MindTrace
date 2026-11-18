"""Email + password teacher sign-up, then creating a first class in the new, empty workspace."""


def _signup(client, **kw):
    body = {"name": "Ms Rao", "email": "rao.signup@example.com", "password": "fractions7"} | kw
    return client.post("/api/auth/teacher/signup", json=body)


def test_signup_then_sign_in_and_create_a_class(client):
    r = _signup(client)
    assert r.status_code == 200, r.text
    H = {"Authorization": f"Bearer {r.json()['token']}"}
    assert r.json()["teacher"]["email"] == "rao.signup@example.com"
    assert client.get("/api/classes", headers=H).json() == []  # a new workspace starts empty
    c = client.post("/api/classes", headers=H, json={"name": " 8 B ", "grade": "8"}).json()
    assert c["name"] == "8 B" and [x["id"] for x in client.get("/api/classes", headers=H).json()] == [c["id"]]
    assert client.post("/api/classes", headers=H, json={"name": "8 B"}).json()["error"] == "class_exists"
    assert client.get(f"/api/classes/{c['id']}/overview", headers=H).json()["student_count"] == 0
    # signs in again with the same password; email is case-insensitive
    again = client.post("/api/auth/teacher/login", json={"email": "Rao.Signup@Example.com", "password": "fractions7"})
    assert again.status_code == 200
    # another teacher can't see the new class
    demo = client.post("/api/auth/teacher/login", json={"email": "teacher@mindtrace.demo", "password": "demo1234"}).json()
    assert client.get(f"/api/classes/{c['id']}/overview", headers={"Authorization": f"Bearer {demo['token']}"}).status_code == 404


def test_signup_validation(client):
    assert _signup(client, email="teacher@mindtrace.demo").json()["error"] == "email_taken"
    assert _signup(client, email="not-an-email", password="abc12345").json()["error"] == "bad_email"
    assert _signup(client, email="x1@example.com", password="short1").json()["error"] == "weak_password"
    assert _signup(client, email="x2@example.com", password="12345678").json()["error"] == "weak_password"
    assert _signup(client, email="x3@example.com", name="   ").json()["error"] == "bad_name"
    assert client.post("/api/classes", json={"name": "9A"}).status_code == 401


def test_gemini_is_offered_only_to_a_google_signed_in_teacher(client, monkeypatch):
    """No MindTrace key: Gemini opens in the teacher's own Google account, so a password session doesn't get it."""
    from app import config
    from app.routes import auth
    pw = client.post("/api/auth/teacher/login", json={"email": "teacher@mindtrace.demo", "password": "demo1234"}).json()
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {pw['token']}"}).json()
    assert me["capabilities"]["gemini_account"] is None
    monkeypatch.setattr(config, "GOOGLE_CLIENT_IDS", ["test-client"])
    monkeypatch.setattr(auth, "_verify_google", lambda c: {"sub": "g-sub-gemini", "email": "new.gemini@gmail.com",
                                                          "email_verified": True, "name": "Gem Teacher"})
    g = client.post("/api/auth/google", json={"credential": "x", "allow_signup": True}).json()
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {g['token']}"}).json()
    assert me["capabilities"]["gemini_account"] == "new.gemini@gmail.com"


def test_google_redirect_checks_csrf_and_hands_token_to_the_page(client):
    r = client.post("/api/auth/google/redirect", data={"credential": "header.payload.sig", "g_csrf_token": "abc"},
                    cookies={"g_csrf_token": "abc"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login#google_credential=header.payload.sig"
    bad = client.post("/api/auth/google/redirect", data={"credential": "x", "g_csrf_token": "abc"},
                      cookies={"g_csrf_token": "other"}, follow_redirects=False)
    assert bad.headers["location"] == "/login#google_error=csrf"
    client.cookies.clear()
    missing = client.post("/api/auth/google/redirect", data={"credential": "x"}, follow_redirects=False)
    assert missing.headers["location"] == "/login#google_error=csrf"
