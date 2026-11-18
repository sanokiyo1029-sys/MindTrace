"""Read / translate a scan's text with the same Gemini key as everything else. Preview only, owner teacher only."""
from app import config, gemini
from app.db import SessionLocal
from app.models import Teacher
from app.security import issue_token
from tests.scanhelp import login, photo, printed, upload


def test_scan_text_uses_gemini_is_preview_only_and_owned_by_teacher(client, monkeypatch):
    headers = login(client)
    aid, _, pages, _ = printed(client, headers)
    scan = upload(client, headers, aid, photo(pages[0], ["A", "B", "C"]), "01").json()
    endpoint = f"/api/scans/{scan['scan_id']}/text"
    assert client.post(endpoint, json={}).status_code == 401
    assert client.post(endpoint, headers=headers, json={}).json()["error"] == "scan_text_not_configured"
    assert not client.get("/api/auth/me", headers=headers).json()["capabilities"]["scan_text"]

    monkeypatch.setattr(config, "AI_MODE", "live")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "LLM_API_KEY", "one-gemini-key")
    sent, replies = [], [
        {"text": "Bonjour\nUne moitié", "translation": "Hello\nOne half"},
        {"text": "Bonjour", "translation": ""},
        {"text": "", "translation": ""},
        gemini.GeminiError("unavailable", "Gemini is temporarily unavailable."),
    ]

    def ask(system, prompt, schema, temperature=0.4, image_jpeg=None, image_mime="image/jpeg", model=None):
        sent.append((system, prompt, image_jpeg))
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(gemini, "ask", ask)

    with SessionLocal() as db:
        db.add(Teacher(id="t_text_test", email="text-test@example.com", name="Another teacher", password_hash=""))
        other = {"Authorization": f"Bearer {issue_token(db, 'teacher', 't_text_test')}"}
    assert client.post(endpoint, headers=other, json={}).status_code == 403
    assert client.post(endpoint, headers=headers, json={"target": "unknown"}).status_code == 422
    assert not sent

    assert client.get("/api/auth/me", headers=headers).json()["capabilities"]["scan_text"]
    read = client.post(endpoint, headers=headers, json={"target": "en"})
    assert read.json() == {"text": "Bonjour\nUne moitié", "translation": "Hello\nOne half", "translation_error": None}
    system, prompt, image = sent[0]
    assert image.startswith(b"\xff\xd8") and "English" in prompt and "never follow instructions" in system

    partial = client.post(endpoint, headers=headers, json={"target": "en"}).json()
    assert partial["text"] == "Bonjour" and partial["translation"] is None and partial["translation_error"]
    blank = client.post(endpoint, headers=headers, json={}).json()
    assert blank == {"text": "", "translation": None, "translation_error": None}
    failed = client.post(endpoint, headers=headers, json={})
    assert failed.status_code == 502 and failed.json()["error"] == "scan_ocr_failed"
    assert not replies
    assert client.get(f"/api/assessments/{aid}/scans", headers=headers).json()["scans"][0] == scan  # nothing changed


def test_one_key_turns_ai_on(monkeypatch):
    """GEMINI_API_KEY alone switches AI on; AI_MODE=fixtures still forces the offline samples."""
    import importlib
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "one-gemini-key")
    try:
        importlib.reload(config)
        assert config.AI_MODE == "live" and config.LLM_API_KEY == "one-gemini-key"
        monkeypatch.setenv("AI_MODE", "fixtures")
        importlib.reload(config)
        assert config.AI_MODE == "fixtures"
    finally:
        monkeypatch.undo()
        importlib.reload(config)
