# MindTrace: How the Parts Combine Into One Product

Three people build three parts in parallel. They only fit together at the end if everyone follows the **same connection points** below. Read this once now, and again before every merge.

```
 Phone / laptop browser
        │  HTTPS (tunnel)
        ▼
 ┌──────────────────────┐   /api/*   ┌──────────────────────────────┐  import  ┌──────────────────────┐
 │ frontend/  (Risheeth)│ ─────────▶ │ backend/  (Rohan)            │ ───────▶ │ backend/app/ai/      │
 │ React + Vite :5173   │ ◀───────── │ FastAPI + SQLite :8000       │ ◀─────── │ (Samrudh)            │
 └──────────────────────┘   JSON     │ PDF · QR · OMR · insights    │  dicts   │ prompts · validators │
            ▲                        └──────────────────────────────┘          └──────────────────────┘
            │ mock mode                              ▲                                   ▲
            └──────────────── tests/fixtures/*.json (Samrudh) ───────────────────────────┘
```

## The 5 connection points (don't change without a PR + group message)

### 1. Frontend ↔ Backend: HTTP + JSON
- Every API path in `docs/CONTRACTS.md` is served under **`/api`** (e.g. `POST /api/assessments/generate`). Backend: `APIRouter(prefix="/api")`.
- Media (scan images, crops) is served at `/api/media/...`, and URLs in responses already include that prefix.
- Backend runs on **:8000**, frontend on **:5173**. `vite.config.js` proxies `/api` → `http://localhost:8000`, so the frontend always calls relative `/api/...` and works the same locally and through the tunnel.
- Field names are exactly those in CONTRACTS. **No renaming** (no `questionId` vs `question_id`). Use snake_case everywhere.
- Errors are always `{ "error": "...", "message": "..." }`. The frontend shows `message`.

### 2. Backend ↔ AI module: a Python import
```python
from app.ai import generate_questions, validate_question, teaching_suggestion, followup_questions
```
- Samrudh's module is **pure functions: dicts in, dicts out**. No FastAPI, no database, no request objects inside `app/ai/`.
- It reads only env vars (`AI_MODE`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`) and files in `prompts/` and `tests/fixtures/`.
- If the LLM fails, it falls back to fixtures and sets `"source": "sample"` on questions. It never raises an error up to the backend.

### 3. Shared data: `tests/fixtures/`
- Samrudh owns it. Every file matches a shape in CONTRACTS.
- Frontend mock mode uses these same files (`npm run sync-fixtures` copies them into `frontend/src/mocks/`).
- Backend `seed.py` loads `roster.json`. AI fixtures mode returns `questions_sample.json`.
- If a fixture changes shape, CONTRACTS changes in the same PR.

### 4. Printed sheet ↔ Scanner: `backend/app/sheet_layout.json`
- Both PDF generation and OMR read this one file (Rohan owns both). Any change means: reprint the test pack (Saniya) and re-test.

### 5. Config: one `.env` at the repo root
- Backend loads `../.env`. Vite uses `envDir: '..'` so it reads the same file (`VITE_*` vars only reach the browser).
- `.env` is never committed. `.env.example` lists every variable name.

## Handoff schedule (who needs what from whom)

| When | From → To | What | Why |
|---|---|---|---|
| **H01** | Samrudh → Rohan | `backend/app/ai/__init__.py` stub: the 4 functions returning fixtures | Rohan can call AI from minute one |
| **H02** | Samrudh → Risheeth | `tests/fixtures/*.json` for every shape | Risheeth builds all screens on mocks |
| **H02** | Rohan → everyone | backend runs, `/api/health` OK, URL in group chat | Everyone can test against it |
| **H04** | Rohan → Risheeth | `generate`, `PATCH question`, `approve`, `print` live | Risheeth switches those screens off mock |
| **H05** | Rohan → Saniya | 5 printed sheets | She makes the physical test pack |
| **H05** | Samrudh → Rohan | real `generate_questions` + `validate_question` (PR) | Live AI behind the same import |
| **H07** | Saniya → Rohan | filled test pack + ground truth | OMR tuning |
| **H09** | Rohan → Risheeth | `scans`, `review`, `confirm` live + HTTPS tunnel URL | Phone scanner works for real |
| **H11** | Samrudh → Rohan | `teaching_suggestion` | Insight cards get real activities |
| **H12** | Rohan → Risheeth | `insights` live | Dashboard off mock |
| **H13** | Samrudh → Rohan | `followup_questions` | Retest loop |
| **H14** | Rohan → Risheeth | `followup`, student login/results live | Last screens off mock |
| **H15** | Saniya → Sree Athira | screenshots + backup video | Deck + fallback |

## Integration checkpoints (merge into `main`, then test together)

Rohan merges. After each checkpoint **everyone pulls `main`** and confirms it runs on their machine.

| # | Time | Merged | Must work on `main` |
|---|---|---|---|
| I1 | H02 | skeletons + fixtures + AI stub | backend + frontend both start; frontend shows mock screens |
| I2 | H05 | create/approve/print + real question generation | **M1:** type concepts → approve → PDF with 5 QR sheets |
| I3 | H09 | scanner + scanner page + tunnel | **M2:** phone scans 5 real sheets → correct IDs + answers |
| I4 | H12 | review/confirm + insights + teaching suggestions | **M3:** confirmed answers → misconception card with evidence |
| I5 | H15 | follow-up + student view | **M4:** complete loop, nothing on mock |
| I6 | H18 | bug fixes only | 3 clean end-to-end runs in a row |
| FREEZE | H21 | — | tag `v1.0-demo`, no more features |

**If a checkpoint fails:** stop new work, fix `main` together first. A late checkpoint pushes stretch goals out, never the core loop.

## Definition of the FINAL product (what "combined" means)

On a fresh `git clone` of `main`, with `.env` filled in, all of this works with **no mock data**:

- [ ] Teacher logs in, enters concepts, gets 3 AI questions (or labelled sample questions if AI is down)
- [ ] Teacher edits one question, approves; invalid questions block approval
- [ ] Print gives 5 personalised A4 sheets with QR codes
- [ ] Phone (over HTTPS) scans a **freshly filled** sheet → correct student + answers within seconds
- [ ] Double-bubbled / faint / duplicate sheets go to review or are flagged, never guessed
- [ ] Teacher confirms → insights show distribution, top *possible* misconception, evidence, 5-minute activity
- [ ] "Create follow-up" → new approved question → printable
- [ ] Student logs in with code + PIN → sees only their own results
- [ ] `AI_MODE=fixtures` still runs the whole loop offline
- [ ] README "Run it locally" works when followed word for word

## Final assembly (H18–H21, Rohan leads, everyone present)

```bash
git checkout main && git pull
cp .env.example .env            # fill in real values

# terminal 1: backend
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --host 0.0.0.0 --port 8000

# terminal 2: build the website once (the backend serves it at http://localhost:8000)
cd frontend && npm install && npm run build

# terminal 3: HTTPS for the phone camera. The printed https://….trycloudflare.com address is the
# whole app: open it, sign in, done. No second address to copy.
cloudflared tunnel --url http://localhost:8000
```
For live UI work, `npm run dev` on :5173 still works (it proxies `/api` to :8000, and accepts `*.trycloudflare.com` hosts).
A quick tunnel gets a new random address every run; for a fixed address, use a named Cloudflare tunnel on your own domain.
Then Saniya runs the test pack and the demo runbook start to finish, Samrudh checks every AI sentence on screen, Risheeth fixes UI issues, Sree Athira times the pitch against the real app.

## Rules that keep the combine painless

1. **Stay in your folder.** Need something in someone else's folder? Ask them, or open an issue.
2. **CONTRACTS is the law.** Changing a field = PR touching CONTRACTS + fixtures + a message in the group.
3. **`main` always runs.** Small PRs every 2–3 hours. Never push straight to `main` (except Rohan's merges).
4. **Pull `main` after every checkpoint** and rebase your branch (`git pull --rebase origin main`).
5. **Mock until it's real, then delete the mock path for that screen.** Nothing on mock at I5.
6. **No secrets in git, no real student data, no faked results.**
