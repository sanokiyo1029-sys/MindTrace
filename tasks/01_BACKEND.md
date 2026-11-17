# Task: Backend + Integration Owner

**Owner:** `@________` · **Branch:** `feat/backend` · **Folder:** `backend/` (not `backend/app/ai/`, that's Research)
**You are also the integration owner:** you review and merge PRs and keep `main` runnable.

Read first: `docs/PROBLEM_STATEMENT.md`, `docs/CONTRACTS.md`, `AGENTS.md`.

## Stack

Python 3.11 · FastAPI · SQLite (SQLModel or SQLAlchemy) · ReportLab + `qrcode` (PDF) · OpenCV + `pyzbar` or `cv2.QRCodeDetector` (scan) · Uvicorn

```
backend/
  app/
    main.py            # FastAPI app, CORS, routers, /health
    db.py, models.py   # Teacher, Class, Student, Assessment, Question, Sheet, Scan, Answer
    seed.py            # demo teacher, class 7A, 5 fictional students from tests/fixtures/roster.json
    routes/            # auth.py, assessments.py, scans.py, insights.py, student.py
    sheet_layout.json  # ONE source of truth for PDF + OMR coordinates (mm)
    pdf.py             # sheet PDF generation
    scanner/           # qr.py, align.py, omr.py
    insights.py        # plain-Python aggregation (no AI)
    ai/                # ← Research owns this; you just import it
  requirements.txt
  README.md            # how to run (keep it to 5 lines)
```

## Build order (each step = one PR)

### B1 · Skeleton (H00–H02)
- [ ] FastAPI app, CORS for the Vite dev URL, `/health` → `{ok, ai_mode}`
- [ ] Models for everything in CONTRACTS §2–7; IDs are random short strings (`as_`, `q_`, `s_`, `sc_` prefixes)
- [ ] `seed.py`: 1 teacher, class `cl_7a`, 5 students (+ PINs) from `tests/fixtures/roster.json`
- [ ] Simple auth: teacher token + student token (signed JWT or random token in DB is fine)
- **Done when:** `uvicorn app.main:app --reload` runs and `/health` works for the frontend

### B2 · Assessments (H02–H04)
- [ ] `POST /assessments/generate` → calls `ai.generate_questions(...)`, runs `ai.validate_question` on each, stores as draft
- [ ] `PATCH /questions/{id}`, `POST /assessments/{id}/approve` (400 if any question invalid or unapproved)
- **Done when:** frontend can create → edit → approve with `AI_MODE=fixtures`

### B3 · Printable sheets (H03–H05) → milestone M1
- [ ] `sheet_layout.json`: A4, 4 solid black corner squares (~10 mm), QR box top-right (~30 mm), per question: stem area, 4 bubbles (~8 mm circles), 2–3 reasoning lines
- [ ] `pdf.py`: one page per student; header = MindTrace · topic · class · student display name · short code `MT-001`; QR = `MT:<sheet_id>`
- [ ] `GET /assessments/{id}/print` → creates `Sheet` rows if missing, returns one combined PDF
- **Done when:** 5 personalised sheets print cleanly with large, high-contrast bubbles

### B4 · Scanner (H05–H09) → milestone M2 ⚠️ the hardest part, start early
- [ ] `POST /assessments/{id}/scans` (multipart `image`)
- [ ] `qr.py`: decode QR → `sheet_id` → look up sheet. Fail → `rejected / qr_not_found` (never guess a student)
- [ ] `align.py`: find the 4 corner squares (threshold → contours → 4 biggest squares) → perspective-warp to a fixed size (e.g. 2100×2970 px = 10 px/mm)
- [ ] Quality checks: blur (variance of Laplacian), darkness (mean brightness), page not found → `rejected` with a reason
- [ ] `omr.py`: for each bubble, crop by layout, adaptive threshold, compute fill ratio
  - one clearly highest above threshold → `single`; none → `blank`; two high → `multiple`; close call → `ambiguous`
  - tune the thresholds **on real printed sheets** with Presenter 2's test pack
- [ ] Save full image + per-question crops (bubble row + reasoning box) to `backend/media/` and return URLs
- [ ] Duplicate: same `sheet_id` already accepted → `duplicate` (unless `?replace=true`)
- **Done when:** 5 freshly filled sheets, photographed on a phone, give correct IDs and options. Ambiguous ones go to review, never a forced guess.
- **Fallback (assisted capture):** if OMR isn't reliable by H09, still decode QR + save crops, set all answers to `needs_review`, and let the teacher tap the answers. It's still a real scan.

### B5 · Review, confirm, insights (H09–H12) → milestone M3
- [ ] `GET /assessments/{id}/scans` progress, `PATCH /scans/{id}/review`, `POST /assessments/{id}/confirm`
- [ ] `insights.py`: per-question distribution → map each wrong option to its `misconception_id` → count students → rank → attach evidence + `ai.teaching_suggestion(...)` + one follow-up question
- [ ] Insights return 409 until `needs_review == 0`
- [ ] Always add `caveats` (e.g. "Handwriting not analysed")

### B6 · Follow-up + student + HTTPS (H12–H15) → milestone M4
- [ ] `POST /assessments/{id}/followup` → new draft assessment with `parent_assessment_id`
- [ ] `POST /auth/student/login`, `GET /student/me/results`. Make sure student A gets 403 for student B's data
- [ ] **Phone camera needs HTTPS.** Easiest: run frontend + backend on the laptop and expose with `cloudflared tunnel --url http://localhost:5173` (Vite proxies `/api` → backend). Or deploy (Render for API, Vercel/Netlify for frontend) if there's time.

### B7 · Hardening (H15–H21)
- [ ] AI down → `/assessments/generate` falls back to fixtures with a visible note, not a crash
- [ ] Bad photo, unknown QR, duplicate, double bubble: all return clear statuses
- [ ] `tests/test_api.py`: smoke test of the full loop with fixture images
- [ ] Freeze at H21, tag `v1.0-demo`

## Integration duties
- Merge PRs from frontend/research after a quick run. Keep `main` always runnable.
- Post the running API URL in the group chat as soon as B1 is up.
- Keep `.env.example` updated (variable names only, **never** real keys).

## Prompt to start your Claude Code session
> Read AGENTS.md, docs/CONTRACTS.md and tasks/01_BACKEND.md. Implement step B1 inside backend/ only. Use FastAPI + SQLite. Stop after B1 and tell me how to run it.
