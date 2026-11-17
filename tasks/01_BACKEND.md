# Task: Backend + Integration Owner

**Owner:** Rohan (`@sanokiyo1029-sys`) · **Branch:** `feat/backend` · **Folder:** `backend/` (not `backend/app/ai/`, that's Research)
**You are also the integration owner:** you review and merge PRs and keep `main` runnable.

Read first: `docs/PROBLEM_STATEMENT.md`, `docs/CONTRACTS.md`, `AGENTS.md`. **How your part plugs into the others: `docs/INTEGRATION.md`.**

## Stack

Python 3.11 · FastAPI · SQLite (SQLModel or SQLAlchemy) · ReportLab (PDF) · Gemini + OpenCV bubble reader (scan; QR was replaced by roll numbers, see docs/CONTRACTS.md §4–7) · Uvicorn

```
backend/
  app/
    main.py            # FastAPI app, CORS, routers, /health
    db.py, models.py   # Teacher, Class, Student, Assessment, Question, Sheet, Scan, Answer
    seed.py            # demo teacher, class 7A, 5 fictional students from tests/fixtures/roster.json
    routes/            # auth.py, assessments.py, scans.py, insights.py, student.py
    sheet_layout.json  # ONE source of truth for PDF + OMR coordinates (mm)
    pdf.py             # sheet PDF generation
    scanner/           # gemini_reader.py, align.py, omr.py, pipeline.py
    insights.py        # plain-Python aggregation (no AI)
    ai/                # ← Research owns this; you just import it
  requirements.txt
  README.md            # how to run (keep it to 5 lines)
```

## Status (updated 17 Nov, first backend push)

Built and passing tests on **synthetic** phone photos (tilt, perspective, dim light, upside down, sideways, blue pen, double bubble, faint mark, duplicate, junk photo). Still to do:
- [ ] **Real paper test** with Saniya's test pack; tune `OMR_FILLED` / `OMR_EMPTY` (see `backend/README.md`)
- [ ] HTTPS tunnel for the phone camera (`cloudflared tunnel --url http://localhost:5173`)
- [ ] Swap in Samrudh's `app/ai/` (the bridge picks it up automatically) and re-run tests
- [ ] Freeze at H21, tag `v1.0-demo`

## Build order (each step = one PR)

### B1 · Skeleton (H00–H02)
- [x] FastAPI app, all routes under `/api` (`APIRouter(prefix="/api")`), CORS for the Vite dev URL, `/api/health` → `{ok, ai_mode}`, media served at `/api/media`
- [x] Models for everything in CONTRACTS §2–7; IDs are random short strings (`as_`, `q_`, `s_`, `sc_` prefixes)
- [x] `seed.py`: 1 teacher, class `cl_7a`, 5 students (+ PINs) from `tests/fixtures/roster.json`
- [x] Simple auth: teacher token + student token (signed JWT or random token in DB is fine)
- **Done when:** `uvicorn app.main:app --reload` runs and `/health` works for the frontend

### B2 · Assessments (H02–H04)
- [x] `POST /assessments/generate` → calls `ai.generate_questions(...)`, runs `ai.validate_question` on each, stores as draft
- [x] `PATCH /questions/{id}`, `POST /assessments/{id}/approve` (400 if any question invalid or unapproved)
- **Done when:** frontend can create → edit → approve with `AI_MODE=fixtures`

### B3 · Printable sheets (H03–H05) → milestone M1
- [x] `sheet_layout.json`: A4, 4 solid black corner squares (~10 mm), QR box top-right (~30 mm), per question: stem area, 4 bubbles (~8 mm circles), 2–3 reasoning lines
- [x] `pdf.py`: one page per student; header = MindTrace · topic · class · student display name · short code `MT-001`; QR = `MT:<sheet_id>`
- [x] `GET /assessments/{id}/print` → creates `Sheet` rows if missing, returns one combined PDF
- **Done when:** 5 personalised sheets print cleanly with large, high-contrast bubbles

### B4 · Scanner (H05–H09) → milestone M2 ⚠️ the hardest part, start early
- [x] `POST /assessments/{id}/scans` (multipart `image`)
- [x] ~~`qr.py`~~ replaced: Gemini reads the handwritten roll number → matched to the assessment's class roster. Unclear/unknown/ambiguous → teacher review (never guess a student)
- [x] `align.py`: find the 4 corner squares (threshold → contours → 4 biggest squares) → perspective-warp to a fixed size (e.g. 2100×2970 px = 10 px/mm)
- [x] Quality checks: blur (variance of Laplacian), darkness (mean brightness), page not found → `rejected` with a reason
- [x] `omr.py`: for each bubble, crop by layout, adaptive threshold, compute fill ratio
  - one clearly highest above threshold → `single`; none → `blank`; two high → `multiple`; close call → `ambiguous`
  - tune the thresholds **on real printed sheets** with Presenter 2's test pack
- [x] Save full image + per-question crops (bubble row + reasoning box) to `backend/media/` and return URLs
- [x] Duplicate: same `sheet_id` already accepted → `duplicate` (unless `?replace=true`)
- **Done when:** 5 freshly filled sheets, photographed on a phone, give correct IDs and options. Ambiguous ones go to review, never a forced guess.
- **Fallback (assisted capture):** if OMR isn't reliable by H09, still decode QR + save crops, set all answers to `needs_review`, and let the teacher tap the answers. It's still a real scan.

### B5 · Review, confirm, insights (H09–H12) → milestone M3
- [x] `GET /assessments/{id}/scans` progress, `PATCH /scans/{id}/review`, `POST /assessments/{id}/confirm`
- [x] `insights.py`: per-question distribution → map each wrong option to its `misconception_id` → count students → rank → attach evidence + `ai.teaching_suggestion(...)` + one follow-up question
- [x] Insights return 409 until `needs_review == 0`
- [x] Always add `caveats` (e.g. "Handwriting not analysed")

### B6 · Follow-up + student + HTTPS (H12–H15) → milestone M4
- [x] `POST /assessments/{id}/followup` → new draft assessment with `parent_assessment_id`
- [x] `POST /auth/student/login`, `GET /student/me/results`. Make sure student A gets 403 for student B's data
- [ ] **Phone camera needs HTTPS.** Easiest: run frontend + backend on the laptop and expose with `cloudflared tunnel --url http://localhost:5173` (Vite proxies `/api` → backend). Or deploy (Render for API, Vercel/Netlify for frontend) if there's time.

### B7 · Hardening (H15–H21)
- [x] AI down → `/assessments/generate` falls back to fixtures with a visible note, not a crash
- [x] Bad photo, unknown QR, duplicate, double bubble: all return clear statuses
- [x] `tests/test_api.py`: smoke test of the full loop with fixture images
- [ ] Freeze at H21, tag `v1.0-demo`

## Integration duties
- Merge PRs from frontend/research after a quick run. Keep `main` always runnable.
- Post the running API URL in the group chat as soon as B1 is up.
- Keep `.env.example` updated (variable names only, **never** real keys).

## Prompt to start your Claude Code session
> Read AGENTS.md, docs/CONTRACTS.md and tasks/01_BACKEND.md. Implement step B1 inside backend/ only. Use FastAPI + SQLite. Stop after B1 and tell me how to run it.
