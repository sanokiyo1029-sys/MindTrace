# Handoff for Codex: where MindTrace stands (18 Nov 2026)

Read `AGENTS.md` and `docs/CONTRACTS.md` first. AGENTS.md rules still apply: match the contract (new fields are additive and listed in the "Additions" sections at the end of CONTRACTS.md), fictional students only, never fake scan/AI results, uncertain scans go to `needs_review`, say "possible misconception", never "weak student".

## Repo state

| What | Where |
|---|---|
| Default branch | `main` @ `a5109d9` (merge of PR #10) |
| Open PR | **#11** `feat/google-gemini-ai` → `main` @ `e085754`, mergeable, not merged yet |
| Merged | PR #10 `feat/web-app` (web app, Android shell, roll-number scanning, the 8 priority features) |
| Local checkout | on `feat/google-gemini-ai` |

Leave these alone (not ours, never committed): the one-line edit in `frontend/src/paper.css`, untracked `demo/scan_log.md` and `docs/BUILD_PROMPT.md`.

## Run and test

```bash
# backend (Python 3.11+, venv already in backend/.venv on the dev PC)
cd backend
.venv\Scripts\python -m pytest -q tests          # 66 tests, all passing on e085754
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# website (the backend serves frontend/dist at http://localhost:8000)
cd frontend
npm ci
npm run build                                     # or: npm run dev  (Vite on :5173, proxies /api to :8000)

# Android app, from source (no APK needed)
npm run build
npx cap sync android
npx cap run android                               # or open frontend/android in Android Studio
# compile check only:  cd android; .\gradlew.bat :app:compileDebugJavaWithJavac
```

Logins (fictional, seeded in `backend/app/seed.py`): teacher `teacher@mindtrace.demo` / `demo1234`; students `7A-01`…`7A-05`, PINs `1111`…`5555`; APK test teacher `apk.tester@mindtrace.demo` / `apk-b3t1uq48` (class 7T).

Tip: for browser testing use a scratch DB so the dev data in `backend/mindtrace.db` stays clean: set `DATABASE_URL=sqlite:///<tmp>/e2e.db` and `MEDIA_DIR=<tmp>/media`, run on another port.

## Map of the code

Backend (`backend/app/`)
- `routes/assessments.py`: generate (subject, difficulty, `num_descriptive`), edit questions (`base_version` → 409 `conflict`), teacher-added questions, approve, print PDF, confirm, follow-up, results.
- `routes/scans.py`: upload (Gemini read + bubble reader cross-check), review (transcriptions, draft saves, `base_version`).
- `routes/teaching.py`: teacher-verified feedback (`/feedback`, `/feedback/suggest`), teaching plan + video links, assigned practice.
- `routes/student.py`: student results (released only after teacher confirms), own scan, approved feedback, practice (once per student).
- `routes/classes.py`: class overview / history by subject, `/students/{id}/report`.
- `routes/media.py`: scan images need a token (owner teacher, or the student once released).
- `routes/ai.py`: **new in #11**, `POST /api/ai/ask` (text and/or one image; actions ask / extract / summarize / describe).
- `routes/auth.py`: password, Google ID token (`/auth/google`, linked teachers only), `/auth/me`, logout; sessions expire after `SESSION_HOURS`.
- `gemini.py`: REST client; `ask(..., schema=None)` returns free text; error kinds `rate_limited`, `unavailable`, `timeout`, `blocked`, `bad_output`, `api_error`, `not_configured`.
- `ai_bridge.py` + `subject_data.py`: question generation for 6 subjects with labelled sample fallbacks.
- `layout.py` / `pdf.py` / `scanner/`: one-page A4 sheet shared by PDF and scanner; written-answer blocks have no bubbles.

Frontend (`frontend/src/`)
- `App.jsx`: routes, teacher workspace, create/review/print/scan screens, Google button (web popup + native).
- `TeacherAreas.jsx`: overview, history, student report, recommendations, feedback review, practice, sync badge, `VideoLink`.
- `StudentHome.jsx`: student dashboard. `AiPage.jsx`: AI assistant. `offline.js`: per-teacher outbox for offline edits. `api.js`: API client.

## What's verified vs not

Verified (tests + browser against a scratch backend, AI off or Gemini mocked at the HTTP call): the full teacher flow, digital PDF → scan round trip, offline edit / conflict / expired-session sync, cross-account privacy (API and direct URLs), AI screen (text, image extraction, image question, retry, quota / unsupported / oversize messages, one request at a time), session restore, sign-out.

**Not verified, needs credentials or hardware:**
1. Real Google sign-in on the website, including the "canceled" message (the browser pane blocked popups from automation).
2. Real Google sign-in in the Android app (`@capgo/capacitor-social-login`, Credential Manager), on a phone or emulator.
3. Real Gemini replies: question drafts for all 6 subjects, page reading (OCR of handwriting), feedback suggestions, AI assistant.
4. Live camera capture and a physically printed-then-photographed sheet.
5. YouTube video playback (only a local test video was played).

## Next tasks, in order

1. **Get credentials into `.env`** (never commit it):
   - Google Cloud → OAuth client **Web application**: JS origins `http://localhost`, `http://localhost:8000`, `http://localhost:5173`, plus the public https address. No redirect URIs.
   - OAuth client **Android**: package `org.mindtrace.app`, SHA-1 of the debug key on the dev PC `F0:4E:49:5E:2C:EB:93:96:8D:C1:47:86:D5:40:44:A2:C7:76:FF:C5` (add the release key later).
   - Consent screen: add test users.
   - `.env`: `GOOGLE_CLIENT_ID=<web client id first>`, `GOOGLE_TEACHER_EMAILS=<allowed google accounts>`, `AI_MODE=live`, `LLM_PROVIDER=gemini`, `LLM_API_KEY=<key from aistudio.google.com/apikey>`, optional `GEMINI_CHAT_MODEL` (default `gemini-3.5-flash-lite`; `gemini-2.5-flash` is deprecated and reroutes on 1 Dec 2026).
2. **Run the unverified checks above** and fix what breaks. For each, note "verified live" in PR #11 before merging it.
3. **Merge PR #11** once the live checks pass (the owner merges; ask first).
4. Known gaps worth doing next (small, each its own PR):
   - The website can't load while offline (no service worker); the Android app bundles it. Decide whether a PWA cache is wanted.
   - `frontend/tests/smoke.js` is a Playwright snippet with no runner installed; either add Playwright or drop it.
   - Google sign-in is limited to linked teacher accounts by design (protects the Gemini quota). If any Google user should use the AI screen, add an explicit allow-list or domain rule, server-side.
   - Image tokens travel as `?token=` in `<img>` URLs (same as the print link). Short-lived signed media URLs would be cleaner.

## Gotchas

- Windows: keep the repo at `C:\Users\meyaa\Desktop\MindTrace` (long paths break Python). Several `.jsx` files use CRLF line endings; scripted string replacements can silently miss.
- `npx cap sync android` after every web build you want in the app.
- Any change to `sheet_layout.json` or the layout code means reprinting test sheets.
- `docs/CONTRACTS.md` is shared: add to the "Additions" sections; don't rename existing fields.
