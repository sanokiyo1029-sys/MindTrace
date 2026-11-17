import os
import sys
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="mindtrace_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'test.db'}"
os.environ["MEDIA_DIR"] = str(Path(_tmp) / "media")
os.environ["AI_MODE"] = "fixtures"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
