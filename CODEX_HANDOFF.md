# CODEX HANDOFF — MindTrace platform expansion

Branch **`feat/platform-expansion`** (local worktree `C:\Users\meyaa\Desktop\mt-platform`, based on `ae3ba51` of
`feat/google-gemini-ai`). **Not pushed yet** and **not deployed**. The live Render demo still runs `ae3ba51`.
Read `AGENTS.md`, `docs/CONTRACTS.md` (bottom sections are new), `docs/PLATFORM_PLAN.md`, `docs/DEPLOY.md` first.

## 1. Project overview
- Teachers print STEM papers, students answer on paper, the teacher photographs them; MindTrace reads bubbles
  (OpenCV, optional Gemini for handwriting), the teacher confirms, and the app shows *possible* misconceptions,
  evidence, teaching activities and follow-up quizzes. Also: student accounts, practice, written answers, marks.
- **Frontend:** React 18 + Vite + react-router (`frontend/src`), Capacitor Android app. The website calls the server it
  was loaded from (`/api`); the APK uses a saved server address. Offline edits: `offline.js` outbox (localStorage).
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2, ReportLab (PDF), OpenCV (bubble reader), optional Gemini REST.
  Serves the built site too (catch-all in `app/main.py`).
- **Database:** SQLite by default, Postgres via `DATABASE_URL`. Tables: teachers, classes (join_code), students
  (account_id, roll_no, pin_hash), student_accounts, password_resets, tokens, assessments, questions (JSON `data`),
  sheets, scans (JSON `answers`), feedback, assignments, practice_submissions, media_blobs. Columns are added by
  `db.migrate()` (`_NEW_COLUMNS`), there is no Alembic.

## 2. Work completed (this branch)
| Commit | What |
|---|---|
| 11c95f5, e489787, 009f996 | **Phase 1 accounts:** student self-sign-up with class join codes, several classes per student, email+password or code+PIN login, login throttling (5 fails / 10 min), forgot/reset password (SMTP or teacher reset or `python -m app.admin reset-link <email>`), profiles, teacher roster page (join code, add/remove/reset students). |
| ea8ba40, 22e296f | **Phase 2 question types:** 17 types in `backend/app/marking.py` (validation, auto-marking with partial credit, paper kind), editor `frontend/src/QuestionTypes.jsx`, question pictures, teacher marks in scan review, marks in results and the student view. |
| 9f107b0 | **Scanning fixes** (see section 4): Postgres support, photos stored in DB, storage banner, loading/error states for the review queue and Choose Student, clear 404 messages, photo shrinking before upload. |

New files: `backend/app/{marking,media_store,mailer,admin}.py`, `backend/app/routes/accounts.py`,
`backend/tests/{test_accounts,test_marking,test_storage}.py`, `frontend/src/{Accounts,QuestionTypes}.jsx`,
`docs/{PLATFORM_PLAN,DEPLOY}.md`. DB changes: tables `student_accounts`, `password_resets`, `media_blobs`; columns
`classes.join_code` (unique), `students.account_id`; question `data` gains `marks`, type-specific keys, `image_url`.

## 3. Work remaining
- **Phase 3 online exams** (not started): exam builder from approved questions, timed player for all 17 types
  (structured responses already marked by `marking.mark(q, response)`), one submission per student, teacher review
  with `teacher_score`, publish results, reports. Reuse practice code in `routes/student.py` as the starting point.
- **Phase 4 offline exams:** service worker + IndexedDB answers, auto-save, sync with duplicate protection, status.
- **Phase 5:** student learning assistant = Gemini *hand-off* only (Gemini API terms forbid under-18 apps), student
  Lens capture → edit → ask. Teacher Gemini/Lens hand-offs already exist (`AiPage.jsx`, `LensPanel` in `App.jsx`).
- **Phase 6:** owner creates a free Postgres (Neon recommended) and sets `DATABASE_URL` on Render (`docs/DEPLOY.md`).
- Known limits: pictures on bubble questions print small; papers mixing bubbles with 3+ written boxes printed before
  ea8ba40 must be reprinted (layout changed); a plain MCQ can't be teacher-added (needs misconception tags).

## 4. Critical issues: Choose Student, Google Lens / scanning, Confirm Paper
**Investigation:** traced UI → `PATCH /api/scans/{id}/review` → DB → response with real clicks on a local server.
Locally all three work (upload → choose student → confirm → Confirm results → insights/dashboard; duplicate paper is
held as "Replace or ignore"). The live demo teacher had **0 assessments** although the owner had been using it:
**root cause = Render free disk is wiped on restart/deploy/after ~15 idle min**, erasing SQLite and photos mid-lesson,
so the queue/roster/scan/photo requests 404 and the old UI failed silently (empty lists, "Nothing to check").
**Fixed in 9f107b0** (tested in the browser): review queue shows Loading/error + Try again; Choose Student shows
loading / "didn't load" + Try again / empty-class states; 404s explain the reset; photos are restored from
`media_blobs`; `/api/health` → `storage: temporary|persistent` drives a red banner; big photos shrink to 2400 px.
**Exact remaining work:**
1. Owner: create the free Postgres and set `DATABASE_URL` on Render, then Manual Deploy (until then data still vanishes).
2. Verify on Postgres for real: `pip install "psycopg[binary]"`, run the app with a Postgres URL, run the flow. **Not
   tested against Postgres yet** (only SQLite). Watch `db.migrate()` raw SQL and JSON columns.
3. Test on a real phone: camera capture, gallery upload, iOS HEIC photos (not shrunk; server may reject them).
4. Android app: `googleapp://lens` hand-off is untested on a device; if it doesn't open, add a Capacitor intent or
   open `https://lens.google.com` in the system browser.
5. Banner UI was not seen in a browser (needs `RENDER=1` + SQLite); backend flag is unit-tested.

## 5. Technical information
- Scanning endpoints: `POST /api/assessments/{id}/scans` (multipart `image`, `roll_number`), `GET /api/assessments/{id}/scans`,
  `PATCH /api/scans/{id}/review` `{answers:[{question_id, final, text, score}], student_id, roll_number, confirmed,
  replace, discard, base_version}`, `POST /api/assessments/{id}/confirm`, `GET /api/assessments/{id}/results`,
  `GET /api/media/scans/{name}?token=`, `GET /api/classes/{id}/students`, `GET /api/health`.
- Questions: `POST /api/assessments/{id}/questions` (any type), `PATCH /api/questions/{id}`,
  `POST|DELETE /api/questions/{id}/image`, `POST /api/assessments/{id}/approve`, `GET .../print` (PDF).
- Accounts: `/api/auth/{teacher,student}/{login,signup}`, `/api/auth/password/{forgot,reset}`, `/api/auth/profile`,
  `/api/student/classes[/join]`, `/api/classes/{id}/{join-code,students,students/{sid}[/reset]}`.
- Components: `App.jsx` (`Scanner`, `ReviewScans`, `ScanReviewCard`, `LensPanel`, `ReviewQuestions`, `useRoster`),
  `QuestionTypes.jsx`, `Accounts.jsx`, `StudentHome.jsx`, `TeacherAreas.jsx`; backend `routes/scans.py`,
  `scanner/` (omr, gemini_reader), `layout.py` + `sheet_layout.json` (shared by PDF and reader), `marking.py`.
- Env vars (names only, see `docs/DEPLOY.md`): `DATABASE_URL`, `MEDIA_DIR`, `AI_MODE`, `GEMINI_API_KEY`,
  `GOOGLE_CLIENT_ID`, `FRONTEND_ORIGIN`, `PUBLIC_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`,
  `SESSION_HOURS`; frontend `VITE_SERVER_URL` (APK), `VITE_MOCK`.
- Run: `cd backend && python -m uvicorn app.main:app --reload` (demo teacher `teacher@mindtrace.demo` / `demo1234`,
  students `7A-01..05`, PINs in `app/demo_data.py`); `cd frontend && npm ci && npm run build` (served by the backend)
  or `npm run dev`. Tests: `cd backend && python -m pytest -q`. On this PC use
  `C:\Users\meyaa\Desktop\MindTrace\backend\.venv\Scripts\python` (bare `python` is the Windows Store stub).

## 6. Testing
- **Passed:** backend `pytest` 81/81. Frontend `npm run build` OK.
- **Browser (local, real clicks):** Phase 1 sign-up/join/login/forgot/reset/teacher reset; Phase 2 authoring of
  numerical, match, graph (+picture), short; approve, print, scan, auto + teacher marks (6.5/9), student view;
  scanning: upload (2 MB photo → 0.3 MB), queue loading state, Choose Student, Confirm Paper, duplicate held,
  discard, Confirm results → insights 2/5 and dashboard marks, missing-assessment message.
- **Failed:** none open.
- **Not yet performed:** Postgres, Render deploy of this branch, real phone camera, iOS HEIC, Android APK Lens,
  storage banner in a browser, frontend automated tests (`frontend/tests/smoke.js` has no runner).

## 7. Exact next steps for Codex
1. `git fetch && git checkout feat/platform-expansion` (once the owner has pushed it). Run the tests.
2. Help the owner set `DATABASE_URL` (Neon) on Render; deploy; check `/api/health` says `persistent`; run one paper
   end to end on the phone (print → photo → Choose Student → Confirm Paper → Confirm results).
3. Do section 4 items 2–5.
4. Start Phase 3 per `docs/PLATFORM_PLAN.md`; keep CONTRACTS additive; add pytest for every new route.
5. Open a PR `feat/platform-expansion` → `main` when 2–3 pass. Never commit secrets; fictional student data only.

## 8. Git status (at handoff)
- Branch `feat/platform-expansion`, latest commit `9f107b0` (+ this handoff commit). Working tree clean apart from it.
- Not pushed to GitHub. Desktop clone `C:\Users\meyaa\Desktop\MindTrace` has unrelated uncommitted files
  (`frontend/src/paper.css`, `demo/scan_log.md`, `docs/BUILD_PROMPT.md`): leave them alone.
