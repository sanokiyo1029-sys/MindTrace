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
# Gemini (server side only, never sent to the browser). AI_MODE=live + LLM_PROVIDER=gemini + LLM_API_KEY turns it on.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip() or "gemini-3.5-flash-lite"
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
# Google sign-in: OAuth client ID(s) from Google Cloud, comma-separated (web now, Android later).
GOOGLE_CLIENT_IDS = [c.strip() for c in os.getenv("GOOGLE_CLIENT_ID", "").split(",") if c.strip()]
# Google accounts (verified emails) allowed to sign in as the demo teacher, comma-separated.
GOOGLE_TEACHER_EMAILS = {e.strip().lower() for e in os.getenv("GOOGLE_TEACHER_EMAILS", "").split(",") if e.strip()}
# Built website, served by the backend at / so one address (or one tunnel) is the whole app.
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", REPO_ROOT / "frontend" / "dist"))

# OMR thresholds: tune these on real printed sheets (see demo/scan_log.md)
OMR_FILLED = float(os.getenv("OMR_FILLED", "0.42"))   # fraction of dark pixels to count as a mark
OMR_EMPTY = float(os.getenv("OMR_EMPTY", "0.18"))     # below this a bubble is clearly empty

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
(MEDIA_DIR / "scans").mkdir(parents=True, exist_ok=True)
