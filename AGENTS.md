# AGENTS.md: context for Claude Code / Codex

## Project
MindTrace: teachers print STEM MCQ sheets (QR per student), students answer on paper, the teacher scans with a phone, and the app shows **possible** class misconceptions, evidence, a teaching activity and a follow-up quiz. 24-hour hackathon MVP: 1 topic (fractions), 3 questions, 5 fictional students.

## Read before coding
1. `docs/CONTRACTS.md`: JSON shapes + API. **Match them exactly.** Don't change them without the human asking.
2. The task file for the area you're working in (`tasks/0X_*.md`).

## Stack
- `backend/`: Python 3.11, FastAPI, SQLite, ReportLab, qrcode, OpenCV. Run: `uvicorn app.main:app --reload` from `backend/`.
- `backend/app/ai/`: AI module. `AI_MODE=fixtures` must work with no network.
- `frontend/`: React + Vite. API base from `VITE_API_URL`; mock mode reads `tests/fixtures/`.

## Rules
- Only edit files in the folder you were asked to work in. Folder owners are in `docs/TEAM_PLAN.md`.
- Keep changes small and runnable; one feature per PR.
- **Never** commit secrets. Keys live in `.env` (git-ignored). Update `.env.example` with variable names only.
- **Never fake results.** No hard-coded scan outputs or insights presented as live. Fixtures are only for mock/offline mode and must be labelled.
- Uncertain scans → `needs_review`; never guess an answer or a student.
- User-facing text: say "possible misconception", show evidence, never "weak student".
- Fictional student data only.
- Add or update a short test when you add logic (pytest for backend, at least a smoke test).
