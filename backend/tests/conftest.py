import os
import sys
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="mindtrace_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'test.db'}"
os.environ["MEDIA_DIR"] = str(Path(_tmp) / "media")
os.environ["AI_MODE"] = "fixtures"
os.environ["GOOGLE_CLIENT_ID"] = ""          # tests turn Google on themselves
os.environ["FRONTEND_DIST"] = str(Path(_tmp) / "dist")
(Path(_tmp) / "dist" / "assets").mkdir(parents=True)
(Path(_tmp) / "dist" / "index.html").write_text("<!doctype html><title>MindTrace test page</title>")
(Path(_tmp) / "dist" / "assets" / "app.js").write_text("console.log(1)")
(Path(_tmp) / "secret.txt").write_text("not for the web")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def gem(monkeypatch):
    """Gemini switched on with its PAGE READINGS faked. Push raw replies (or exceptions) onto gem["readings"].
    Text calls (question drafts, activities) fail on purpose, so those use the labelled samples."""
    from app import config, gemini

    monkeypatch.setattr(config, "AI_MODE", "live")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    state = {"readings": [], "calls": []}

    def fake_ask(system, prompt, schema, temperature=0.4, image_jpeg=None):
        if image_jpeg is None:
            raise gemini.GeminiError("api_error", "text calls are not part of these tests")
        state["calls"].append({"prompt": prompt, "schema": schema, "image_bytes": len(image_jpeg)})
        r = state["readings"].pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(gemini, "ask", fake_ask)
    return state
