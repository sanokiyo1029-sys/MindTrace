# MindTrace: Shared Contracts (FREEZE THIS FIRST)

Backend, frontend and research all build against this file. **Change it only by PR, and tell the team in the group chat.**
Sample JSON for every shape lives in `tests/fixtures/` (research owns it). Frontend mocks from those fixtures until the API is live.

---

## 1. Misconception (library entry, research owns)

```json
{
  "id": "M_ADD_DENOMS",
  "topic": "fractions",
  "label": "Adds denominators as well as numerators",
  "student_friendly": "You may have added the bottom numbers too. The bottom number tells the size of each piece, and that stays the same.",
  "teaching_activity": {
    "title": "Fraction strips: same-size pieces",
    "minutes": 5,
    "steps": ["Show 1/3 + 1/3 with two strips", "Ask: did the pieces get smaller?", "Write 2/3 and compare with 2/6"]
  }
}
```

## 2. Question

```json
{
  "id": "q_001",
  "assessment_id": "as_001",
  "topic": "fractions",
  "concept": "adding fractions with equal denominators",
  "stem": "What is 1/3 + 1/3?",
  "options": { "A": "2/6", "B": "2/3", "C": "1/6", "D": "1/3" },
  "answer": "B",
  "explanation": "Same denominator: add the numerators, keep the denominator. 1/3 + 1/3 = 2/3.",
  "distractors": {
    "A": { "misconception_id": "M_ADD_DENOMS", "why": "Added top and bottom numbers" },
    "C": { "misconception_id": "M_MULTIPLY_INSTEAD", "why": "Multiplied the fractions" },
    "D": { "misconception_id": "M_IGNORE_SECOND", "why": "Ignored the second fraction" }
  },
  "difficulty": "easy",
  "status": "draft",
  "source": "ai"
}
```
- `status`: `draft` | `approved`. An assessment can't print unless **all** questions are approved.
- `source`: `ai` | `teacher` | `sample` (offline fallback).

## 3. Assessment

```json
{
  "id": "as_001",
  "class_id": "cl_7a",
  "title": "Fractions check 1",
  "topic": "fractions",
  "concepts_text": "We taught adding fractions with equal denominators and LCM for unequal denominators.",
  "questions": ["<Question>", "..."],
  "status": "draft",
  "parent_assessment_id": null
}
```
- `status`: `draft` → `approved` → `printed` → `scanning` → `confirmed`
- `parent_assessment_id` is set on follow-up quizzes (used for before/after).

## 4. Student & Sheet

```json
{ "id": "st_01", "class_id": "cl_7a", "display_name": "Aarav", "student_code": "7A-01", "roll_no": "01" }
```
```json
{ "sheet_id": "s_8f3k2a9x", "short_code": "MT-001", "assessment_id": "as_001", "student_id": "st_01" }
```
- **`roll_no`** is what the student writes at the top of the paper. Always a **string** (keeps leading zeros, allows `12B`), **unique within a class** only, so two classes can both have `01`. `student_code` stays the school-wide login ID.
- A **sheet** is the internal per-student paper record for one assessment (made at print time, or when a late joiner's paper is scanned). It links scans and results to the student. Nothing about it is printed.
- Printed copies are **identical**: no names, no QR, no per-student code. Identity comes only from the handwritten roll number, matched against **the selected assessment's class roster**.
- Fictional student names only, never real minors' data.

## 5. Sheet layout (backend owns; PDF and the bubble reader share it)

`backend/app/sheet_layout.json` holds page size, the 4 corner marker positions, the **roll-number boxes, class/section box and page/paper-code block at the top**, and for each question the bubble centres (A–D) and the reasoning box, all in **mm from top-left of A4**. PDF generation and the bubble reader both read this one file. Never hard-code coordinates twice. One page per paper (`Page 1 of 1`); the printed **paper code** is the assessment id without its prefix (e.g. `as_e1wscjn4` → `E1WSCJN4`).

## 6. ScanResult (response of `POST /assessments/{id}/scans`)

```json
{
  "scan_id": "sc_001",
  "status": "needs_review",
  "reject_reason": null,
  "sheet_id": "s_8f3k2a9x",
  "short_code": "MT-001",
  "student": { "id": "st_01", "display_name": "Aarav", "roll_no": "01" },
  "roll_number": { "read": "01", "status": "matched", "candidates": ["st_01"] },
  "extracted_by": "gemini",
  "warnings": [ { "code": "answers_unclear", "message": "Some answers are unclear. Choose them from the photo." } ],
  "answers": [
    {
      "question_id": "q_001",
      "detected": null,
      "state": "multiple",
      "note": "",
      "confidence": null,
      "final": null,
      "crop_url": "/api/media/scans/sc_001_q1.jpg",
      "reasoning_crop_url": "/api/media/scans/sc_001_q1_why.jpg"
    }
  ],
  "image_url": "/api/media/scans/sc_001.jpg",
  "duplicate_of": null
}
```
- **Every new scan is `needs_review`.** The teacher confirms the student and the answers (`PATCH /scans/{id}/review`) before anything counts. Scores and insights use only confirmed answers and the approved answer key.
- `status`: `accepted` (teacher-confirmed) | `needs_review` | `duplicate` (the student already has a confirmed paper; not counted) | `rejected` (discarded by the teacher).
- `roll_number.status`: `matched` | `unknown` (not on the class roster) | `ambiguous` (more than one possible student; `candidates` lists them) | `unreadable`. Never guessed. `7` may match `07` only if that is the only possibility (warning `roll_loose_match`).
- `extracted_by`: `gemini` | `bubble_reader` (Gemini unavailable or its reply was invalid; the deterministic reader filled the answers) | `manual` (nothing readable; the teacher enters answers) | `qr_legacy` (scans made before roll numbers).
- `state` per answer: `single` | `blank` | `multiple` | `ambiguous` | `unreadable`. Only `single` (→ its letter) and `blank` pre-fill `final`; the others leave `final: null` for the teacher. When Gemini and the bubble reader disagree, the answer becomes `ambiguous` with a `note`.
- `confidence` is `null`: model self-reports are not treated as probabilities.
- `warnings[].code`: `roll_unreadable`, `roll_unknown`, `roll_ambiguous`, `roll_loose_match`, `answers_unclear`, `ai_unavailable`, `ai_output_invalid`, `ai_off`, `ai_inconsistent`, `other_assessment`, `page_mismatch`, `class_mismatch`, `already_confirmed`, `too_dark`, `too_blurry`, `page_not_found`, `blurry`, `glare`, `cropped`, `incomplete_page`, `not_an_exam_page`, `crossed_out_marks`. Show `message`.
- One **live** scan per student per assessment. A newer upload replaces an unconfirmed one; a confirmed one is only replaced with `replace` (query `?replace=true` on upload, or `"replace": true` on review). Enforced in the database too.
- Upload errors (no scan stored): `415 not_an_image`, `413 too_large` (over 15 MB), `400 bad_image`, `409 not_printed`.

Scan progress (`GET /assessments/{id}/scans`):
```json
{ "total": 5, "accepted": 3, "needs_review": 1, "remaining": 1, "scans": ["<ScanResult>"], "duplicates": [], "rejected": [] }
```

## 7. Review (`PATCH /scans/{scan_id}/review`)

```json
{ "answers": [ { "question_id": "q_001", "final": "A" } ], "student_id": "st_01", "confirmed": true }
```
`final` may be `"A"|"B"|"C"|"D"|"blank"`. Identity: `student_id` (must be in the assessment's class) **or** `roll_number` (matched against that class). `confirmed: true` needs a student and a `final` for every answer. `"replace": true` confirms a `duplicate` over the existing confirmed paper. `"discard": true` removes the photo from the queue.

## 8. InsightReport (`GET /assessments/{id}/insights`)

```json
{
  "assessment_id": "as_001",
  "papers": { "printed": 5, "verified": 5, "needs_review": 0, "missing": 0 },
  "questions": [
    { "question_id": "q_001", "correct": 2, "total": 5, "distribution": { "A": 3, "B": 2, "C": 0, "D": 0, "blank": 0 } }
  ],
  "misconceptions": [
    {
      "misconception_id": "M_ADD_DENOMS",
      "label": "Adds denominators as well as numerators",
      "status": "possible",
      "students_affected": 3,
      "evidence": [ { "question_id": "q_001", "option": "A", "count": 3 } ],
      "why_we_think_so": "3 of 5 students chose 2/6 for 1/3 + 1/3, which matches adding both top and bottom numbers.",
      "uncertainty": "A wrong option is evidence of an incorrect answer, not proof of the reasoning. Some may be guesses.",
      "teaching_action": { "title": "Fraction strips: same-size pieces", "minutes": 5, "steps": ["..."] },
      "followup_question": "<Question>"
    }
  ],
  "caveats": ["Handwriting not analysed (OCR disabled)"],
  "generated_by": "rules+ai"
}
```
- Insights only appear when `needs_review == 0` (all scans confirmed).
- `status` is always `possible` unless the teacher marks it `confirmed`.
- No student names in the class report. Names are shown only in the teacher's per-student view.

## 9. Student report (`GET /student/me/results`, ID + PIN login)

```json
{
  "student": { "display_name": "Aarav" },
  "assessments": [
    {
      "assessment_id": "as_001",
      "title": "Fractions check 1",
      "answers": [ { "question_id": "q_001", "stem": "What is 1/3 + 1/3?", "chosen": "A", "correct": "B", "explanation": "...", "maybe": "You may have added the bottom numbers too..." } ]
    }
  ]
}
```
A student can only ever see their own results. Requesting another student's → `403`.

---

## API list (backend owns)

All paths below are served under the **`/api`** prefix (e.g. `POST /api/assessments/generate`). Media URLs in responses already start with `/api/media/`. See `docs/INTEGRATION.md`.

| Method | Path | Body / Notes | Returns |
|---|---|---|---|
| POST | `/auth/teacher/login` | `{email, password}`, one seeded demo teacher | `{token}` |
| POST | `/auth/student/login` | `{student_code, pin}` | `{token}` |
| GET | `/auth/config` | public; what the sign-in screen can offer | `{google_client_id}` (`null` = Google sign-in off) |
| POST | `/auth/google` | `{credential}` = Google ID token. Linked **teachers** only (verified email = a teacher's email or in `GOOGLE_TEACHER_EMAILS`); never student access | `{token, teacher}`; 403 `google_not_linked` |
| POST | `/auth/logout` | ends the session for the sent token (any role) | `{ok}` |
| GET | `/classes/{id}/students` | | `Student[]` |
| POST | `/assessments/generate` | `{class_id, topic, concepts_text, num_questions}` | `Assessment` (draft) |
| PATCH | `/questions/{id}` | partial `Question` (teacher edits) | `Question` |
| POST | `/assessments/{id}/approve` | 400 if any question invalid | `Assessment` |
| GET | `/assessments/{id}/print` | creates sheets if missing | `application/pdf` |
| POST | `/assessments/{id}/scans` | multipart `image` (JPG/PNG, max 15 MB), optional form field `roll_number` typed by the teacher (+ `?replace=true`). Gemini reads the page; always returns `needs_review` (or `duplicate`) | `ScanResult` |
| GET | `/assessments/{id}/scans` | | progress object (+ `duplicates`) |
| PATCH | `/scans/{id}/review` | Review body | `ScanResult` |
| POST | `/assessments/{id}/confirm` | locks results | `Assessment` |
| GET | `/assessments/{id}/insights` | | `InsightReport` |
| POST | `/assessments/{id}/followup` | `{misconception_ids: []}` | new draft `Assessment` |
| GET | `/student/me/results` | student token | Student report |
| GET | `/health` | | `{ok, ai_mode, ai_module_loaded, ai_provider}` |
| GET | `/classes` | teacher's classes | `[{id, name, grade}]` |
| GET | `/assessments` | teacher's assessments, newest first | `[{id, title, topic, status, ...}]` |
| GET | `/assessments/{id}` | | `Assessment` |
| GET | `/assessments/{id}/results` | teacher-only per-student view | `[{student, roll_no, short_code, scan_status, correct, total, answers}]` |

Errors are always `{ "error": "code", "message": "human text" }`.

**Auth:** send `Authorization: Bearer <token>`. For links the browser opens directly (the print PDF), `?token=<token>` also works.

**Extra fields the backend adds** (safe to ignore):
- Assessment: `notes` (e.g. `"Using saved sample questions (AI unavailable)"`). Show it in the UI.
- Question: `validation_errors` (list of strings; approve is blocked until all are empty) and `edited_by_teacher`.
- Scan progress: `duplicates` (papers waiting for a Replace decision) and `rejected` (teacher-discarded photos are left out). `remaining` = printed papers with no live scan yet.
- Health: `ai_provider` = `app.ai` | `gemini` | `samples` (who answers AI calls right now).
- InsightReport `teaching_action`: `source` = `ai` | `sample`. Questions keep `source` (`ai` | `teacher` | `sample`); show it.

## AI module interface (research owns `backend/app/ai/`)

```python
generate_questions(topic: str, concepts_text: str, n: int, grade: str) -> list[dict]   # Question dicts, status="draft"
validate_question(q: dict) -> list[str]                                               # [] means valid
teaching_suggestion(misconception_id: str, evidence: list[dict]) -> dict              # {title, minutes, steps}
followup_questions(misconception_ids: list[str], n: int) -> list[dict]                # new Question dicts
```
- `AI_MODE=live` calls the LLM. `AI_MODE=fixtures` returns `tests/fixtures/*.json` with no network. **Fixtures mode must always work** (demo backup).
- Aggregating counts into misconceptions is plain Python in the backend (`insights.py`), not AI.

---

## Additions (Nov 2026, backwards compatible)

Everything above still holds. Older MCQ-only assessments and scans need no change: a missing `type` means `"mcq"`.

**Subjects and written answers**
- `POST /assessments/generate` also takes `subject` (`mathematics` default, `physics`, `chemistry`, `biology`, `engineering`, `technology`; anything else → 400 `bad_subject`), `difficulty` (`easy|medium|hard`, optional) and `num_descriptive` (0–2, counted inside `num_questions`). Assessments return `subject` and `plan`.
- Question `type`: `mcq` | `descriptive`. A descriptive question has `stem`, `concept`, optional `model_answer` (teacher-only notes) and `look_for` (misconception ids); no `options`/`answer`. Questions carry `version` (bumped on each edit).
- `POST /assessments/{id}/questions` → teacher adds a question (default `descriptive`); max 5 per paper. Returns `Assessment`.
- `PATCH /questions/{id}` accepts optional `base_version`; stale → 409 `conflict` with `current` (the server copy). Assigned practice can't be edited (409 `already_assigned`).
- Sheet layout: a descriptive block is 1.6× taller, has no bubbles and one lined answer box (`layout.question_blocks(n, types)`). Still one A4 page per paper.

**Scans**
- Each answer also has `text` (transcribed reasoning/notes, or the written answer) and `text_state`: `clear` | `unclear` | `missing` | `not_read` (no AI) | `teacher` (corrected by the teacher). Written answers have `type: "descriptive"`; their `final` is `answered` | `blank`, pre-filled only when the handwriting was read clearly. New warning `handwriting_unclear`.
- ScanResult has `version`. Review answers may omit `final` (keep it) and may include `text`; the body may include `base_version` (stale → 409 `conflict` with `current`). `confirmed: false` saves a draft.
- `/api/media/scans/...` now needs a token (header or `?token=`): the owning teacher, or the student whose paper it is once released.

**Feedback, plan, practice (teacher)**
- `GET /assessments/{id}/feedback` → `{items, ai_available}`: one item per written answer and per wrong bubble answer on confirmed papers, with the response, a `suggestion` (`state`: `ok` | `not_requested` | `unavailable` | `too_unclear`; `source`: `ai` | `library`), `text`, `concept`, `video_url`, `status` (`pending` | `approved` | `dismissed`), `version`.
- `POST /assessments/{id}/feedback/suggest` → asks the AI for readable written answers only; failures are recorded per item.
- `PATCH /feedback/{id}` `{text?, concept?, video_url?, status?, base_version?}`. Approving needs text.
- `PUT /assessments/{id}/plan/{misconception_id}` `{title, minutes, steps, video_url, status: planned|dismissed, note}` → the assessment's `plan`.
- `POST /assessments/{id}/assign` (approved only) and `GET /assessments/{id}/practice` → submission status per student.
- `GET /classes/{id}/overview?subject=` → `{class, subject, student_count, assessment_count, topics, needs_review, concept_coverage, history}`.
- `GET /classes/{id}/overview?subject=…&include_understanding=true` adds teacher-only `understanding` with `students` (id, display name, roll number), `concepts` (name, topic, assessment IDs, up to three observed wrong answer choices), and `results` (correct and answered counts per student, concept, and assessment). Drafts, pending/replaced scans and ungraded written answers contribute no scores. A teacher-confirmed blank MCQ counts as incorrect.
- `GET /students/{id}/report` → one student's papers (teacher of that class only; others 404).

**Student**
- `GET /student/me/results` items add `status` (`released` | `awaiting_review`), `topic`, `subject`, `created_at`, and when released: `score {correct, total}` (bubble questions only), `scan_url`, `feedback` (approved only: `{question_id, concept, text, video_url}`). Released = paper confirmed **and** assessment confirmed.
- `GET /student/me/practice`, `POST /student/me/practice/{assignment_id}` `{answers: [{question_id, choice?|text?}]}`: once per student; a repeat returns the first submission with `already_submitted: true`. No answer key before submitting.

**Auth**
- `GET /auth/me` → `{role, teacher}` or `{role, student}`. Sessions expire after `SESSION_HOURS` (default 168) → 401 `session_expired`.
- Teacher sessions include `capabilities: {gemini_account}`: the Google email when the session came from "Continue with Google", else null. Gemini opens on gemini.google.com as that account (no MindTrace API key); Google applies the account's own plan. Google sign-in does not expose subscription status.
- `POST /auth/google` also accepts `allow_signup: true`. A new verified Google identity gets a separate teacher account with no classes, keyed by the verified Google subject identifier. If that email belongs to an existing Google signup with a different subject, the API returns 409 `google_account_conflict`. Existing email-based teacher links require a Gmail or Google Workspace identity.
- `POST /auth/google` with `role: "student"` links the verified Google identity to an existing student using `student_link: {student_code, pin}`. Subsequent requests can omit `student_link`. Returns `{token, student}` with a student-only session. A Google identity and student can each have one student link.


**Gemini and Google Lens (no API keys)**
- Gemini: the website opens `https://gemini.google.com/app?authuser=<google email>` in a popup (the Gemini app on phones) with the question copied. Only for Google-signed-in teachers.
- Lens: Scan review shares the photo to Google Lens on phones, copies it and opens lens.google.com on computers, and opens Lens's camera (`googleapp://lens`) in the Android app. Lens has no public API.
- Removed: `POST /ai/ask` and `POST /scans/{id}/text`. Server-side Gemini (question drafts, paper reading) is optional via `GEMINI_API_KEY`; without it the labelled samples and the bubble reader are used.


**Question types and marking (Phase 2, backwards compatible; code: `backend/app/marking.py`)**
- `type`: `mcq` | `multi_select` | `true_false` | `fill_blank` | `match` | `assertion_reason` | `one_word` | `short` | `long` | `essay` | `maths` | `numerical` | `diagram` | `image` | `programming` | `code` | `graph` (and the older `descriptive`). Every question may have `marks` (0.5–20, default 1), `image_url`, `code`, `model_answer`.
- Answer keys: `multi_select` → `options` (2–4, A–D) + `answers` (letters); `true_false` → `answer` A (True) / B (False); `assertion_reason` → `answer` A–D (fixed standard options); `fill_blank` → `blanks` (one list of accepted answers per `___`); `match` → `pairs` ([left, right]); `one_word` → `accepted`; `numerical` → `value`, `tolerance`, `unit`. `maths`/`diagram`/`image`/`code`/`graph` are teacher-marked unless they carry `options`+`answer`, `value` or `accepted`. `short`/`long`/`essay`/`programming`/`descriptive` are always teacher-marked; student code is never run.
- Partial credit: multiple select (right − wrong ticks, never below 0), fill in the blanks (per blank), match (per pair). Text is compared ignoring case, spacing and a final full stop; numbers within `tolerance` (fractions like 7/8 accepted).
- Paper: `mcq`, `true_false`, `assertion_reason` and choice-keyed flexible types print as bubbles (only their options); everything else prints a written box with its options / items to match / code / picture. Bubble questions keep their all-bubble height on mixed papers. Pictures: `POST /questions/{id}/image` (multipart `image`, JPG/PNG ≤ 6 MB, re-encoded) and `DELETE /questions/{id}/image`; served at `/api/media/questions/…` to the class's teacher and students.
- `POST /assessments/{id}/questions` takes any type and its key fields; `PATCH /questions/{id}` may change them (approval validates every type).
- Scans: each answer gains `score`, `max_score`, `scored_by` (`teacher` | `auto` | null = to mark) and the scan gains `score`, `max_score`, `to_mark`. Review answers may include `score` (0..marks, partial allowed; `null` returns it to auto-marking). Written answers auto-mark from the transcription once it is clear or typed by the teacher.
- `GET /assessments/{id}/results` rows and the student's released results add `score`, `max_score`, `to_mark` (`correct`/`total` still count bubble questions only). Student answers, practice questions and feedback items add `written` (bubble vs written box).
