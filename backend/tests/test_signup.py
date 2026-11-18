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
