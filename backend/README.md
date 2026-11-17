# backend/

Owner: Rohan (`tasks/01_BACKEND.md`). `app/ai/` is owned by Samrudh (`tasks/03_RESEARCH_PROMPTING.md`).
Contracts: `docs/CONTRACTS.md` · How it connects: `docs/INTEGRATION.md`

## Run

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
- Tests: `python -m pytest -q tests` (full loop on synthetic phone photos)

## What's in here

| File | What it does |
|---|---|
| `app/main.py` | FastAPI app, all routes under `/api`, media at `/api/media`, `{error, message}` errors |
| `app/routes/` | auth, classes, assessments (generate/edit/approve/print/confirm/follow-up/results), scans, insights, student |
| `app/ai_bridge.py` | **Only** place that calls Samrudh's `app/ai/`. Falls back to built-in samples if it's missing or fails. Always runs the maths check on answer keys. |
| `app/sheet_layout.json` + `app/layout.py` | One source of truth for where things are printed and where the scanner looks |
| `app/pdf.py` | A4 sheets: corner markers, QR `MT:<sheet_id>`, bubbles, "why" box |
| `app/scanner/` | `align.py` finds the 4 corner squares and flattens the photo (handles tilt, upside-down, sideways); `qr.py` reads the sheet id; `omr.py` reads bubbles → `single` / `blank` / `multiple` / `ambiguous` |
| `app/insights.py` | Plain-Python counting: wrong options → possible misconceptions + evidence; top 3 get a teaching activity + follow-up question |
| `app/demo_data.py` | Fallback questions, misconception library and roster (used until `tests/fixtures/` has them) |

## Tuning the scanner on real paper

Thresholds are env vars (in the root `.env`):
- `OMR_FILLED=0.42`: share of dark pixels inside a bubble to count as a mark
- `OMR_EMPTY=0.18`: below this the bubble is clearly empty; between the two means **ambiguous → teacher review**

Each scan response includes `fill` per option. Log them in `demo/scan_log.md` while testing Saniya's test pack and adjust.

## Extra endpoints (beyond the contract table, for the frontend)

`GET /api/classes` · `GET /api/assessments` · `GET /api/assessments/{id}` · `GET /api/assessments/{id}/results` (teacher-only per-student view)
