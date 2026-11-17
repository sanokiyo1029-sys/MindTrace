# Task: Research & Development (AI module + prompting owner)

**Owner:** Samrudh (`@SamrudhNandakumar`) · **Branch:** `feat/ai` · **Folders:** `backend/app/ai/`, `prompts/`, `tests/fixtures/`, `docs/misconceptions/`

You own the "brain": the misconception library, every prompt, the validators, and the sample data everyone else builds on. Your fixtures are what frontend and backend use **before** the real thing works, so ship them first.

Read first: `docs/PROBLEM_STATEMENT.md`, `docs/CONTRACTS.md` (§1, §2, AI module interface), `AGENTS.md`. **How your part plugs into the others: `docs/INTEGRATION.md`.**

## R1 · Fixtures first (H00–H02) ← others are waiting on this
- [ ] **By H01:** `backend/app/ai/__init__.py` exporting the 4 functions from CONTRACTS (`generate_questions`, `validate_question`, `teaching_suggestion`, `followup_questions`) that just return fixture data. Push it so Rohan can import it right away; you fill in the real logic behind the same names later
- [ ] `tests/fixtures/roster.json`: 5 **fictional** students `{id, display_name, student_code, pin}`
- [ ] `tests/fixtures/misconceptions_fractions.json`: 6–8 entries (shape in CONTRACTS §1). Suggested:
  - `M_ADD_DENOMS`: adds denominators too (1/3 + 1/3 = 2/6)
  - `M_MULTIPLY_INSTEAD`: multiplies instead of adds
  - `M_IGNORE_SECOND`: ignores the second fraction
  - `M_NO_COMMON_DENOM`: adds unlike fractions without a common denominator (1/2 + 1/3 = 2/5)
  - `M_LCM_ERROR`: finds the common denominator but doesn't scale the numerators
  - `M_BIGGER_DENOM_BIGGER`: thinks 1/8 > 1/4 because 8 > 4
  - `M_WHOLE_NUMBER_BIAS`: treats numerator and denominator as separate whole numbers
- [ ] `tests/fixtures/questions_sample.json`: 3 approved demo questions (the *frozen demo quiz*), each with all 3 distractors tagged
- [ ] `tests/fixtures/assessment_sample.json`, `scan_result_sample.json`, `insights_sample.json`, `student_results_sample.json`: one example of each shape in CONTRACTS
- **Done when:** frontend can build every screen from these files

## R2 · Question generation (H02–H05)
- [ ] `prompts/generate_questions.md`: system + user prompt. Must:
  - take `topic`, `concepts_text`, `n`, `grade`
  - return **JSON only** matching the Question shape
  - pick each wrong option on purpose: one known misconception per distractor, using IDs from the library (give the library in the prompt)
  - stay inside the concepts the teacher typed, at the right grade level
- [ ] `backend/app/ai/client.py`: one `call_llm(system, user) -> str` function, provider set by env (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`), with timeout + 1 retry
- [ ] `backend/app/ai/questions.py`: `generate_questions(...)`: call → parse JSON → validate → drop or repair bad items. `AI_MODE=fixtures` returns `questions_sample.json`
- [ ] `backend/app/ai/validate.py`: `validate_question(q) -> list[str]`:
  - exactly 4 options A–D, no duplicates, answer is one of them
  - every wrong option has a `misconception_id` that exists in the library
  - **maths check in code** for fraction arithmetic: parse the stem with `fractions.Fraction`, compute, confirm the answer option equals it and no distractor does
  - stem under ~25 words (fits the sheet)

### LLM for the app ⚠️ read this
ChatGPT Plus and Claude Code subscriptions **don't give an API key** the app can call. Options:
1. **Google AI Studio (Gemini API)**: has offered a free tier; check today's limits. Fine for a demo.
2. A few dollars of OpenAI or Anthropic API credit if someone has it.
3. **Fixtures mode** (no key): always works. The demo must survive with only this.

Keep the key in `.env` (git-ignored). Never commit it or paste it into chats.

## R3 · Prompt testing (H05–H09)
- [ ] `prompts/tests/lessons.md`: 10 realistic teacher inputs (short, messy, Hinglish phrasing, unlike denominators, comparison of fractions, word problems)
- [ ] Run each, record results in `prompts/tests/results.md`: valid? maths correct? distractors meaningful? grade-appropriate?
- [ ] Fix the prompt until ≥ 9/10 pass the validator. Note what you changed and why (judges love this)

## R4 · Teaching suggestions + student text (H09–H12)
- [ ] `prompts/teaching_suggestion.md` + `backend/app/ai/teach.py` → `teaching_suggestion(misconception_id, evidence)` returns `{title, minutes: 5, steps: [3–5]}`. Concrete, needs only board/paper, no blame
- [ ] Student-friendly lines in the library (`student_friendly`): supportive, starts with "You may have…", gives one tip
- [ ] Fixtures fallback: use the library's own `teaching_activity` when AI is off

## R5 · Follow-up questions (H12–H15)
- [ ] `prompts/followup.md` + `backend/app/ai/followup.py` → `followup_questions(misconception_ids, n)`: **new numbers**, same concept, tests transfer (e.g. 2/5 + 1/5 after 1/3 + 1/3); validated with the same validator

## R6 · Honesty + research (H15–H21)
- [ ] Review every user-facing AI sentence: "possible", show evidence, admit uncertainty, no "weak student"
- [ ] `docs/misconceptions/fractions.md`: short write-up of the common fraction misconceptions we use, **with real sources** (textbooks, NCERT material, research papers you actually opened). Presenters will use this. Don't invent citations.
- [ ] `docs/DISCLOSURES.md`: add which parts used AI help and which LLM the app calls
- [ ] Help Presenter 2 with scanner QA if your part is done

## Prompt to start your Claude Code session
> Read AGENTS.md, docs/CONTRACTS.md and tasks/03_RESEARCH_PROMPTING.md. Create the R1 fixture files in tests/fixtures/ exactly matching the shapes in CONTRACTS.md. Use fictional names only. Then stop.

Then for R2:
> Implement backend/app/ai/ (client.py, questions.py, validate.py) per the AI module interface in CONTRACTS.md, with AI_MODE=fixtures fallback. Add pytest tests for validate.py including a wrong-answer-key case.
