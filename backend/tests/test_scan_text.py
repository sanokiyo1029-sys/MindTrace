import base64

import httpx

from app import config
from app.db import SessionLocal
from app.models import Teacher
from app.scanner import cloud_text
from app.security import issue_token
from tests.scanhelp import login, photo, printed, upload


def test_google_scan_text_is_preview_only_and_owned_by_teacher(client, monkeypatch):
    headers = login(client)
    aid, _, pages, _ = printed(client, headers)
    scan = upload(client, headers, aid, photo(pages[0], ["A", "B", "C"]), "01").json()
    endpoint = f"/api/scans/{scan['scan_id']}/text"
    assert client.post(endpoint, json={}).status_code == 401
    assert client.post(endpoint, headers=headers, json={}).json()["error"] == "scan_text_not_configured"
    monkeypatch.setattr(config, "GOOGLE_SCAN_API_KEY", "test-cloud-key")

    sent = []
    replies = [
        (200, {"responses": [{"fullTextAnnotation": {"text": "Bonjour\nUne moitié"}}]}),
        (200, {"data": {"translations": [{"translatedText": "Hello\nOne half"}]}}),
        (200, {"responses": [{"fullTextAnnotation": {"text": "Bonjour"}}]}),
        (503, {}),
        (200, {"responses": [{}]}),
        (200, {"responses": [{"error": {"code": 13, "message": "Internal error"}}]}),
    ]

    def post(url, *, json, headers, timeout):
        sent.append((url, json))
        assert headers["x-goog-api-key"] == "test-cloud-key"
        status, document = replies.pop(0)
        return httpx.Response(status, json=document, request=httpx.Request("POST", url))

    monkeypatch.setattr(cloud_text.httpx, "post", post)
    with SessionLocal() as db:
        db.add(Teacher(id="t_cloud_test", email="cloud-test@example.com", name="Another teacher", password_hash=""))
        other = {"Authorization": f"Bearer {issue_token(db, 'teacher', 't_cloud_test')}"}
    assert client.post(endpoint, headers=other, json={}).status_code == 403
    assert client.post(endpoint, headers=headers, json={"target": "unknown"}).status_code == 422
    assert not sent

    assert client.get("/api/auth/me", headers=headers).json()["capabilities"]["scan_text"]
    read = client.post(endpoint, headers=headers, json={"target": "en"})
    assert read.json() == {"text": "Bonjour\nUne moitié", "translation": "Hello\nOne half", "translation_error": None}
    assert sent[0][0] == cloud_text.VISION_URL
    request = sent[0][1]["requests"][0]
    assert request["features"] == [{"type": "DOCUMENT_TEXT_DETECTION"}]
    assert base64.b64decode(request["image"]["content"]).startswith(b"\xff\xd8")
    assert sent[1] == (cloud_text.TRANSLATE_URL, {"q": "Bonjour\nUne moitié", "target": "en", "format": "text"})

    partial = client.post(endpoint, headers=headers, json={"target": "en"}).json()
    assert partial["text"] == "Bonjour" and partial["translation"] is None and partial["translation_error"]
    blank = client.post(endpoint, headers=headers, json={"target": "en"}).json()
    assert blank == {"text": "", "translation": None, "translation_error": None}
    assert client.post(endpoint, headers=headers, json={}).json()["error"] == "scan_ocr_failed"
    assert not replies
    assert client.get(f"/api/assessments/{aid}/scans", headers=headers).json()["scans"][0] == scan
