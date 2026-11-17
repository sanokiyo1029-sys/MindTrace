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
