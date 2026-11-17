# Task: Frontend

**Owner:** Risheeth (`@risheeth26233`) · **Branch:** `feat/frontend` · **Folder:** `frontend/`

Read first: `docs/PROBLEM_STATEMENT.md`, `docs/CONTRACTS.md`, `AGENTS.md`. **How your part plugs into the others: `docs/INTEGRATION.md`.**

## Stack

React + Vite (JS or TS) · React Router · plain CSS or Tailwind · `fetch` wrapper in `src/api.js`
Mobile-first: the **scanner page runs on the teacher's phone**. Everything else should work on laptop and phone.

```
frontend/src/
  api.js            # all calls; MOCK mode reads tests/fixtures JSON until backend is live
  pages/
    Login.jsx          # teacher login + "I'm a student" link
    NewAssessment.jsx  # class, topic, concepts textarea, number of questions (1–5)
    ReviewQuestions.jsx# edit stem/options/answer, see distractor tags, Approve
    Print.jsx          # open/download PDF, "sheets ready" state
    Scanner.jsx        # camera, capture, live progress
    ReviewScans.jsx    # queue of needs_review / rejected, fix answers, Confirm
    Insights.jsx       # class report + misconception cards + follow-up
    StudentLogin.jsx, StudentResults.jsx
  components/        # QuestionCard, MisconceptionCard, ProgressBar, BubblePicker, StatusToast
```

## Build order (each step = one PR)

### F1 · Skeleton + mock API (H00–H02)
- [ ] Vite app, routes, simple layout with the MindTrace name
- [ ] `api.js` with `VITE_API_URL` and a `MOCK=true` switch that returns fixture JSON (copy from `tests/fixtures/`)
- [ ] Vite dev proxy: `/api` → `http://localhost:8000` (no rewrite; backend serves under `/api`), `envDir: '..'`, and `npm run sync-fixtures` copying `../tests/fixtures/*.json` → `src/mocks/`

### F2 · Create + approve (H02–H05) → supports M1
- [ ] NewAssessment form → `POST /assessments/generate` → loading state ("Drafting questions…")
- [ ] ReviewQuestions: editable stem, 4 options, answer selector, explanation; show each wrong option's misconception label as a small tag
- [ ] Approve button disabled until every question is valid; show backend validation errors inline
- [ ] Print page: button opens `GET /assessments/{id}/print` PDF in a new tab

### F3 · Scanner (H05–H09) → supports M2 ⚠️ most important screen
Layout (from the plan):
- **Top:** "Fractions · Class 7A". **3/5 scanned · 1 needs review · 1 remaining**
- **Middle:** live camera preview (`getUserMedia({video:{facingMode:"environment"}})`) with a page-shaped guide overlay + status text: *Hold steady / Captured ✓ / Duplicate / Too dark / QR not found*
- **Bottom:** `Start` · `Capture` · `Upload image` · `Stop` · `Review (n)`
- [ ] Capture = draw video frame to `<canvas>` → JPEG blob → `POST /assessments/{id}/scans`
- [ ] **Upload fallback:** `<input type="file" accept="image/*" capture="environment">`. Works even without HTTPS, so it's our safety net
- [ ] After each capture show the result for ~2 s (student name + detected A/B/C/D or the reject reason), then ready for next
- [ ] Poll or refetch `GET /assessments/{id}/scans` for the progress counts
- Note: the camera only works on **HTTPS or localhost**. Backend sets up the tunnel; test on your phone early.
- Manual capture button first. Auto-capture is a stretch goal only if manual is solid.

### F4 · Review + Insights (H09–H12) → supports M3
- [ ] ReviewScans: list each scan with status badge; for `needs_review` show the bubble crop image + a 4-button picker (A/B/C/D/blank); `rejected` shows reason + "rescan"
- [ ] "Confirm results" only enabled when nothing needs review
- [ ] Insights page:
  - summary row: papers verified / missing
  - per-question bar of A/B/C/D counts (correct one highlighted)
  - **Misconception cards**: label, *"Possible"* badge, students affected, evidence ("3 of 5 chose 2/6"), *why we think so*, *uncertainty* line, teaching activity steps, follow-up question
  - caveats shown in small text (e.g. "Handwriting not analysed")
  - button: "Create follow-up quiz"

### F5 · Follow-up + Student view (H12–H15) → supports M4
- [ ] Follow-up → reuse ReviewQuestions → Print
- [ ] StudentLogin (student code + PIN) → StudentResults: own answers, correct answer, simple explanation, supportive "you may have…" line. **Never** show other students.
- [ ] (if time) before/after comparison on Insights when a follow-up is confirmed

### F6 · Polish (H15–H21)
- [ ] Every API error shows a human message (no blank screens); AI-down shows "Using saved sample questions"
- [ ] Big tap targets on phone, readable on a projector
- [ ] Wording: never "weak student"; always "possible misconception"
- [ ] Freeze at H21

## Design notes
- Clean and calm: white background, one accent colour, large type. Judges will see it on a projector and a phone.
- Show evidence next to every claim (counts, crop images). That's our trust story.

## Prompt to start your Claude Code session
> Read AGENTS.md, docs/CONTRACTS.md and tasks/02_FRONTEND.md. Build step F1 in frontend/ only with React + Vite, using mock data from tests/fixtures. Stop after F1 and tell me how to run it.
