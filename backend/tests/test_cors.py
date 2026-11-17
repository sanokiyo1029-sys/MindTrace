"""The Android app (Capacitor) calls the API from https://localhost / capacitor://localhost."""
import pytest

PREFLIGHT = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"}


@pytest.mark.parametrize("origin", ["https://localhost", "capacitor://localhost", "http://localhost:5173"])
def test_app_origins_allowed(client, origin):
    r = client.options("/api/auth/teacher/login", headers={"Origin": origin, **PREFLIGHT})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin


def test_other_origins_blocked(client):
    r = client.options("/api/auth/teacher/login", headers={"Origin": "https://example.com", **PREFLIGHT})
    assert "access-control-allow-origin" not in r.headers
