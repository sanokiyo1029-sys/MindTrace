# MindTrace platform expansion: audit and phased plan (18 Nov 2026)

Branch `feat/platform-expansion` (worktree `C:\Users\meyaa\Desktop\mt-platform`), started from `feat/google-gemini-ai` @ `ae3ba51`.
The paper-to-insight loop (generate → approve → print → scan → teacher review → possible misconceptions → teaching plan →
follow-up) stays the core. Everything below adds to it; nothing in it is removed or mocked.

## 1. Audit

### Working (tested, in production code)
- **Paper loop:** question drafting for 6 STEM subjects (labelled samples without AI), MCQ + written-answer questions,
  teacher edit/approve, one-page A4 PDF per student, phone/upload scanning (bubble reader; Gemini reading optional),
  roll-number matching to the class, teacher review with transcription, duplicates, confirm, insights with evidence,
  teaching plans (with video links), follow-up quizzes, teacher-verified feedback, per-student reports, history,
  class/concept understanding (Codex).
- **Accounts:** teacher email/password sign-up + sign-in, Google sign-in (redirect mode, live), student code + PIN
  sign-in, optional student Google link, session expiry, role-checked API (teacher vs student), private scan images.
- **Students:** released results, own scans, approved feedback, assigned practice (MCQ/text, once each), topic progress.
- **Offline:** teacher question edits and scan reviews queue on the device (localStorage outbox) and sync with conflict checks.
- **Gemini / Lens (no keys):** Gemini opens in the teacher's own Google account; Lens hand-off in scan review.
- **Android shell:** Capacitor app wrapping the same website (native Google sign-in coded, no Android OAuth client yet).
- **Tests:** 65 backend tests (pytest).

### Partial
- **Practice assignments** are a minimal "online quiz": MCQ + free text, auto-marked MCQ only, no timing, no partial credit.
- **Roster management:** new teachers can create classes but cannot add students; demo classes are seeded.
- **Offline:** only teacher edits; the website itself can't load offline (no service worker); the app bundles it.
- **Frontend tests:** `frontend/tests/smoke.js` is a Playwright snippet with no runner installed.

### Missing
- Student self-registration, class join codes, multiple classes per student.
- Password recovery, profile management, login rate limiting.
- Question types beyond MCQ/written: multiple select, true/false, fill blanks, match, assertion-reason, one-word, short,
  long/essay, numerical (tolerance), maths, diagram/image, programming/code, graph interpretation.
- Online examinations (timed, released results), manual marking with partial credit, exam reports.
- Offline examinations (IndexedDB + service worker, sync, duplicate protection).
- Student learning assistant and student Lens capture flow.

### Changes required
- **Database:** `student_accounts`, `password_resets`, `classes.join_code`, `students.account_id`; later `exams`,
  `exam_attempts`, `answers` with marks; question `type` values and structured answer keys (kept in the JSON `data`).
- **Backend:** account/profile/reset routes, class roster routes, marking engine, exam routes, student assistant handoff
  data (no AI calls for students, see 1.2).
- **Frontend:** sign-up/sign-in for students, forgot/reset password, profile, class management, exam builder, exam
  player (online/offline), marking screen, student assistant + Lens capture.

### Security risks found
- **Data loss:** production uses SQLite and local media on Render's free instance; every deploy wipes them. Code is
  ready for `DATABASE_URL` (Postgres) but needs a database the owner creates (see 1.3).
- No login rate limiting (brute force of 4-digit PINs is cheap). Added in Phase 1.
- Tokens in `?token=` URLs (PDF, images) can leak through history/logs. Later: short-lived signed media URLs.
- PBKDF2 at 100k iterations; acceptable now, raise or switch to scrypt later.
- Google consent screen is in Testing mode (only listed test users).

### 1.2 Gemini: what is legitimately possible
- The Gemini API has a free tier (Google AI Studio key, no billing) for Flash/Flash-Lite models; free-tier content may be
  used to improve Google products and read by human reviewers; per-model limits are shown in AI Studio.
- The API terms (effective 23 Mar 2026) say: users must be 18+, and API clients must not be "directed towards or likely to
  be accessed by individuals under the age of 18"; the API is "not for consumer use".
- **Therefore:** no student-facing Gemini API chat. Students get a designed hand-off to the Gemini app in their own Google
  account (Google's consumer age rules apply there). Teacher-side server AI stays optional and modular (`GEMINI_API_KEY`).
- Embedding gemini.google.com in an iframe is not supported; it opens in its own window/app.
- Google Lens has no public API (uploads from other sites return 403); hand-off = share sheet (phones), copy + paste into
  lens.google.com (computers), Lens camera (Android app). No Cloud Vision.

### 1.3 Free infrastructure options (nothing paid is activated)
- **Database:** Render PostgreSQL free (expires after 30 days), Neon free tier, Supabase free tier. Needs the owner to
  create it and paste `DATABASE_URL` into Render.
- **Files (scan photos):** Render disks are paid; free options are Cloudflare R2 / Supabase Storage free tiers (later).
- **Email (password reset):** any SMTP account, e.g. a Gmail app password or a free transactional tier. Without SMTP,
  teachers reset student passwords and an admin command makes teacher reset links.

## 2. Phased plan (each phase: tests + browser check + deploy only on request)

| Phase | Scope | Status |
|---|---|---|
| 1 | Accounts: student sign-up with class join codes, multiple classes per student, email/password student login (code + PIN still works), password recovery (SMTP or teacher/admin reset), profile, login rate limiting; teacher roster management (codes, add/remove/reset students) | **done**: 72 backend tests pass; browser-checked sign-up, join 2nd class, email login, forgot/reset, teacher reset |
| 2 | Question types + marking engine (auto-mark objective types, manual marking with partial credit), printable layout for the new objective types where the sheet allows | **done**: 17 types, 79 backend tests pass; browser-checked authoring, picture upload, approve, print, scan review with auto + teacher marks, results and the student view |
| 3 | Online examinations: publish from an approved assessment, timed player, submissions, review, release and reports | **implemented locally** in `feat/online-exams` |
| 4 | Offline examinations: download an active exam, reopen it offline, save locally, and sync safely before the server deadline | **implemented locally** in `feat/offline-exams` |
| 5 | Student Lens capture, editable question, and hint, explanation or practice prompts on the web. Lens-only APK. | implemented |
| 6 | Persistence + deployment: Postgres via `DATABASE_URL`, file storage, Render settings, docs | planned (needs owner's database) |
