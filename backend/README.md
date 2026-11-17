# backend/

Owner: Rohan (`tasks/01_BACKEND.md`). `app/ai/` is owned by Samrudh (`tasks/03_RESEARCH_PROMPTING.md`).
Contracts: `docs/CONTRACTS.md` · How it connects: `docs/INTEGRATION.md`

## Run

**Quick start:** double-click `start-backend.bat` (Windows) or run `./start-backend.sh` (Mac/Linux) from the repo root. It installs everything on the first run and opens the API docs.

Manual:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
The first start creates `mindtrace.db` and the demo data automatically. API docs: http://localhost:8000/docs

- **Teacher login:** `teacher@mindtrace.demo` / `demo1234`
- **Students (code / PIN):** `7A-01`/`1111`, `7A-02`/`2222`, `7A-03`/`3333`, `7A-04`/`4444`, `7A-05`/`5555` (fictional; from `tests/fixtures/roster.json` once Samrudh adds it)
- Fresh start: `python -m app.seed --reset`
- Tests: `python -m pytest -q tests` (full loop on synthetic phone photos, Gemini mocked)

## Roll numbers + Gemini scanning

**Workflow:** select the assessment → print identical papers (roll-number boxes at the top, no QR, no names) → students write their roll number → photograph each paper → Gemini reads the roll number and the marks → the roll number is matched to **that assessment's class** → the teacher checks and confirms each paper → scores (from the approved answer key) and insights.

**Gemini setup (repo-root `.env`, server only):** `AI_MODE=live`, `LLM_PROVIDER=gemini`, `LLM_API_KEY=<key from https://aistudio.google.com/apikey>`. Optional `LLM_VISION_MODEL` (model for reading photos; defaults to `LLM_MODEL`, which defaults to `gemini-3.5-flash-lite`). Without a key, scanning still works: the bubble reader fills the answers and the teacher types the roll number (labelled "bubble reader" / "manual").

**Live check** (after adding the key): restart, open `/api/health` (expect `"ai_provider":"gemini"`), print one paper, write a roll number and fill some bubbles, photograph it on the Scan papers screen, and compare the review card with the paper.

**Database migration:** automatic and idempotent at every start (`app/db.py: migrate()`, also run by `python -m app.seed`). It adds `students.roll_no` (backfilled from the student code: `7A-01` → `01`, or the full code if that would clash), a unique index on `(class_id, roll_no)`, the scan columns `roll_number`, `extracted_by`, `identity`, `warnings`, and a partial unique index allowing one live scan per student. Older scans keep working and are labelled `extracted_by = qr_legacy`; older printed sheets with QR codes are no longer read (reprint with the new layout). Nothing is deleted.

## What's in here

| File | What it does |
|---|---|
| `app/main.py` | FastAPI app, all routes under `/api`, media at `/api/media`, `{error, message}` errors |
| `app/routes/` | auth, classes, assessments (generate/edit/approve/print/confirm/follow-up/results), scans, insights, student |
| `app/ai_bridge.py` | **Only** place that calls Samrudh's `app/ai/`. Falls back to built-in samples if it's missing or fails. Always runs the maths check on answer keys. |
| `app/sheet_layout.json` + `app/layout.py` | One source of truth for where things are printed and where the scanner looks |
| `app/pdf.py` | Identical A4 papers: roll-number boxes, class/section, page + paper code at the top; corner markers, bubbles, "why" box. No QR, no names |
| `app/scanner/` | `gemini_reader.py` sends the photo to Gemini (strict schema) and validates the reply; `align.py` finds the 4 corner squares and flattens the photo (tilt, sideways; `pipeline.upright` fixes upside-down via the roll boxes); `omr.py` is the deterministic bubble reader (cross-check + fallback) |
| `app/rolls.py` | Roll-number normalising and roster matching (one class only; never guesses between students) |
| `app/insights.py` | Plain-Python counting: wrong options → possible misconceptions + evidence; top 3 get a teaching activity + follow-up question |
| `app/demo_data.py` | Fallback questions, misconception library and roster (used until `tests/fixtures/` has them) |

## Tuning the scanner on real paper

Thresholds are env vars (in the root `.env`):
- `OMR_FILLED=0.42`: share of dark pixels inside a bubble to count as a mark
- `OMR_EMPTY=0.18`: below this the bubble is clearly empty; between the two means **ambiguous → teacher review**

Each scan response includes `fill` per option. Log them in `demo/scan_log.md` while testing Saniya's test pack and adjust.

## Extra endpoints (beyond the contract table, for the frontend)

`GET /api/classes` · `GET /api/assessments` · `GET /api/assessments/{id}` · `GET /api/assessments/{id}/results` (teacher-only per-student view)
