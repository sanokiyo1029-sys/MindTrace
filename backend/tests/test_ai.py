"""AI assistant route: auth, validation, Gemini request shape and error mapping. Gemini's HTTP call is faked."""
import base64

import httpx
import pytest

from app import config, gemini
from tests.scanhelp import login

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(config, "AI_MODE", "live")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(config, "GEMINI_CHAT_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setattr(gemini, "_cooldown_until", 0.0)
    monkeypatch.setattr(gemini.time, "sleep", lambda s: None)
    sent, replies = [], []

    def post(url, body, timeout=None):
        sent.append((url, body))
        r = replies.pop(0)
        return r if isinstance(r, httpx.Response) else httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": r}]}, "finishReason": "STOP"}]})
    monkeypatch.setattr(gemini, "_post", post)
    return sent, replies


def _ask(client, H, **kw):
    files = {"image": (kw.pop("name", "shot.png"), kw.pop("image"), kw.pop("mime", "image/png"))} if "image" in kw else None
    return client.post("/api/ai/ask", headers=H, data=kw, files=files)


def test_needs_a_teacher_session(client):
    assert client.post("/api/ai/ask", data={"prompt": "hi"}).status_code == 401
    s = client.post("/api/auth/student/login", json={"student_code": "7A-01", "pin": "1111"}).json()
    assert client.post("/api/ai/ask", data={"prompt": "hi"},
                       headers={"Authorization": f"Bearer {s['token']}"}).status_code == 401


def test_not_configured_is_clear(client):
    r = _ask(client, login(client), prompt="hello")
    assert r.status_code == 503 and r.json()["error"] == "ai_not_configured"


def test_text_prompt_and_free_text_reply(client, live):
    sent, replies = live
    replies.append("Fractions are parts of a whole.")
    r = _ask(client, login(client), prompt="What is a fraction?")
    assert r.status_code == 200 and r.json()["text"] == "Fractions are parts of a whole."
    url, body = sent[-1]
    assert "gemini-3.5-flash-lite:generateContent" in url
    assert "responseJsonSchema" not in body["generationConfig"]  # free text, not JSON
    assert "What is a fraction?" in body["contents"][0]["parts"][0]["text"]


def test_extract_text_sends_the_image_and_keeps_line_breaks(client, live):
    sent, replies = live
    replies.append("Line one\nLine [unreadable] two")
    r = _ask(client, login(client), action="extract", image=PNG)
    assert r.json()["text"] == "Line one\nLine [unreadable] two"
    parts = sent[-1][1]["contents"][0]["parts"]
    assert parts[0]["inlineData"] == {"mimeType": "image/png", "data": base64.b64encode(PNG).decode()}
    assert "line breaks" in parts[1]["text"] and "[unreadable]" in parts[1]["text"]
    replies.append("It shows a fraction bar.")
    r = _ask(client, login(client), prompt="What does this show?", image=JPG, name="p.jpg", mime="image/jpeg")
    assert r.status_code == 200 and sent[-1][1]["contents"][0]["parts"][0]["inlineData"]["mimeType"] == "image/jpeg"


def test_validation(client, live, monkeypatch):
    H = login(client)
    assert _ask(client, H).json()["error"] == "empty_request"
    assert _ask(client, H, action="describe").json()["error"] == "image_required"
    assert _ask(client, H, action="hack", prompt="x").json()["error"] == "bad_action"
    r = _ask(client, H, image=b"GIF89a....", name="a.gif", mime="image/gif")
    assert r.status_code == 415 and r.json()["error"] == "unsupported_image"
    r = _ask(client, H, image=b"%PDF-1.7", name="fake.png", mime="image/png")  # extension lies: content is checked
    assert r.status_code == 415
    from app.routes import ai
    monkeypatch.setattr(ai, "MAX_IMAGE_BYTES", 32)
    assert _ask(client, H, image=PNG).json()["error"] == "image_too_large"
    assert _ask(client, H, prompt="x" * 4001).json()["error"] == "prompt_too_long"
    assert not live[0]  # nothing invalid reached Gemini


@pytest.mark.parametrize("status,code,retryable", [
    (429, "ai_quota", True), (503, "ai_unavailable", True), (500, "ai_unavailable", True), (403, "ai_error", False)])
def test_gemini_failures_are_explained(client, live, status, code, retryable):
    sent, replies = live
    replies.extend([httpx.Response(status, text="{}")] * 3)
    r = _ask(client, login(client), prompt="hello")
    assert r.json()["error"] == code and r.json()["retryable"] is retryable and r.json()["message"]
    # retry after a temporary failure works
    replies.clear()
    gemini._cooldown_until = 0.0
    replies.append("Back again.")
    assert _ask(client, login(client), prompt="hello").json()["text"] == "Back again."
