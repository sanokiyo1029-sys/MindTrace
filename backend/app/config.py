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
# Optional server-side Gemini key. MindTrace needs NO key: without one, question drafts use the labelled saved samples
# and papers are read by the bubble reader for teacher review. The AI assistant opens Gemini in the teacher's own Google
# account instead (no key). If GEMINI_API_KEY (or LLM_API_KEY) is set, AI drafting and paper reading switch on.
LLM_API_KEY = (os.getenv("GEMINI_API_KEY", "") or os.getenv("LLM_API_KEY", "")).strip()
AI_MODE = os.getenv("AI_MODE", "").strip() or ("live" if LLM_API_KEY else "fixtures")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip() or "gemini-3.5-flash-lite"
# Model that reads photographed papers (handwritten roll numbers, bubbles). Defaults to LLM_MODEL.
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL", "").strip() or LLM_MODEL
# Google sign-in: OAuth client ID(s) from Google Cloud, comma-separated (web now, Android later).
GOOGLE_CLIENT_IDS = [c.strip() for c in os.getenv("GOOGLE_CLIENT_ID", "").split(",") if c.strip()]
# Google accounts (verified emails) allowed to sign in as the demo teacher, comma-separated.
GOOGLE_TEACHER_EMAILS = {e.strip().lower() for e in os.getenv("GOOGLE_TEACHER_EMAILS", "").split(",") if e.strip()}
# Built website, served by the backend at / so one address (or one tunnel) is the whole app.
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", REPO_ROOT / "frontend" / "dist"))

# Sign-in sessions end after this many hours (teacher and student); the app then asks to sign in again.
SESSION_HOURS = float(os.getenv("SESSION_HOURS", "168"))

# OMR thresholds: tune these on real printed sheets (see demo/scan_log.md)
OMR_FILLED = float(os.getenv("OMR_FILLED", "0.42"))   # fraction of dark pixels to count as a mark
OMR_EMPTY = float(os.getenv("OMR_EMPTY", "0.18"))     # below this a bubble is clearly empty

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
(MEDIA_DIR / "scans").mkdir(parents=True, exist_ok=True)
