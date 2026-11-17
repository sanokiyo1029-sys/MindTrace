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
{ "id": "st_01", "class_id": "cl_7a", "display_name": "Aarav", "student_code": "7A-01" }
```
```json
{ "sheet_id": "s_8f3k2a9x", "short_code": "MT-001", "assessment_id": "as_001", "student_id": "st_01" }
```
- **QR payload = `MT:<sheet_id>` only.** No names or personal data in the QR.
- `sheet_id` is random (not sequential). `short_code` is printed for manual entry if the QR fails.
- Fictional student names only, never real minors' data.

## 5. Sheet layout (backend owns; PDF and OMR must share it)

`backend/app/sheet_layout.json` holds page size, the 4 corner marker positions, QR box, and for each question the bubble centres (A–D) and the reasoning box, all in **mm from top-left of A4**. PDF generation and OMR both read this one file. Never hard-code coordinates twice.

## 6. ScanResult (response of `POST /assessments/{id}/scans`)

```json
{
  "scan_id": "sc_001",
  "status": "needs_review",
  "reject_reason": null,
  "sheet_id": "s_8f3k2a9x",
  "short_code": "MT-001",
  "student": { "id": "st_01", "display_name": "Aarav" },
  "answers": [
    {
      "question_id": "q_001",
      "detected": "A",
      "state": "single",
      "confidence": 0.96,
      "fill": { "A": 0.61, "B": 0.05, "C": 0.04, "D": 0.03 },
      "final": null,
      "crop_url": "/api/media/scans/sc_001_q1.png",
      "reasoning_crop_url": "/api/media/scans/sc_001_q1_why.png"
    }
  ],
  "image_url": "/api/media/scans/sc_001.jpg",
  "duplicate_of": null
}
```
- `status`: `accepted` | `needs_review` | `duplicate` | `rejected`
- `reject_reason`: `qr_not_found` | `page_not_found` | `too_blurry` | `too_dark` | `unknown_sheet` | null
- `state` per answer: `single` | `blank` | `multiple` | `ambiguous`. Anything other than a confident `single` → `needs_review`.
- `final` is filled by the teacher's review (or copied from `detected` when accepted).
- Same `sheet_id` scanned again → `duplicate`, count unchanged. Replacing needs `?replace=true`.

Scan progress (`GET /assessments/{id}/scans`):
```json
{ "total": 5, "accepted": 3, "needs_review": 1, "remaining": 1, "scans": ["<ScanResult>"] }
```

## 7. Review (`PATCH /scans/{scan_id}/review`)

```json
{ "answers": [ { "question_id": "q_001", "final": "A" } ], "confirmed": true }
```
`final` may be `"A"|"B"|"C"|"D"|"blank"`.

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
| GET | `/classes/{id}/students` | | `Student[]` |
| POST | `/assessments/generate` | `{class_id, topic, concepts_text, num_questions}` | `Assessment` (draft) |
| PATCH | `/questions/{id}` | partial `Question` (teacher edits) | `Question` |
| POST | `/assessments/{id}/approve` | 400 if any question invalid | `Assessment` |
| GET | `/assessments/{id}/print` | creates sheets if missing | `application/pdf` |
| POST | `/assessments/{id}/scans` | multipart `image` (+ `?replace=true`) | `ScanResult` |
| GET | `/assessments/{id}/scans` | | progress object |
| PATCH | `/scans/{id}/review` | Review body | `ScanResult` |
| POST | `/assessments/{id}/confirm` | locks results | `Assessment` |
| GET | `/assessments/{id}/insights` | | `InsightReport` |
| POST | `/assessments/{id}/followup` | `{misconception_ids: []}` | new draft `Assessment` |
| GET | `/student/me/results` | student token | Student report |
| GET | `/health` | | `{ok, ai_mode}` |

Errors are always `{ "error": "code", "message": "human text" }`.

## AI module interface (research owns `backend/app/ai/`)

```python
generate_questions(topic: str, concepts_text: str, n: int, grade: str) -> list[dict]   # Question dicts, status="draft"
validate_question(q: dict) -> list[str]                                               # [] means valid
teaching_suggestion(misconception_id: str, evidence: list[dict]) -> dict              # {title, minutes, steps}
followup_questions(misconception_ids: list[str], n: int) -> list[dict]                # new Question dicts
```
- `AI_MODE=live` calls the LLM. `AI_MODE=fixtures` returns `tests/fixtures/*.json` with no network. **Fixtures mode must always work** (demo backup).
- Aggregating counts into misconceptions is plain Python in the backend (`insights.py`), not AI.
