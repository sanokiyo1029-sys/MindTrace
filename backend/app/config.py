"""Settings. Reads the single repo-root .env (see docs/INTEGRATION.md)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
load_dotenv(REPO_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'mindtrace.db'}")
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", BACKEND_DIR / "media"))
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
AI_MODE = os.getenv("AI_MODE", "fixtures")

# OMR thresholds: tune these on real printed sheets (see demo/scan_log.md)
OMR_FILLED = float(os.getenv("OMR_FILLED", "0.42"))   # fraction of dark pixels to count as a mark
OMR_EMPTY = float(os.getenv("OMR_EMPTY", "0.18"))     # below this a bubble is clearly empty

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
(MEDIA_DIR / "scans").mkdir(parents=True, exist_ok=True)
