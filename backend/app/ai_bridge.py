"""The ONLY place the backend talks to the AI module.

Samrudh owns `backend/app/ai/` and exposes (docs/CONTRACTS.md -> "AI module interface"):
    generate_questions, validate_question, teaching_suggestion, followup_questions

Until that module exists, or if it raises at runtime, we fall back to the built-in demo
data so the full loop always works (AI_MODE=fixtures behaviour). Nothing here is shown to
users as "AI" when it came from the fallback: questions carry source="sample".
"""
from __future__ import annotations

import copy
import json
import logging
import re
import threading
from fractions import Fraction

from app import demo_data, gemini
from app.config import FIXTURES_DIR

log = logging.getLogger("mindtrace.ai")

try:  # Samrudh's module
    from app import ai as _ai  # type: ignore
    _HAS_AI = all(hasattr(_ai, n) for n in
                  ("generate_questions", "validate_question", "teaching_suggestion", "followup_questions"))
except Exception:  # pragma: no cover - depends on teammate's code
    _ai = None
    _HAS_AI = False


def ai_module_loaded() -> bool:
    return _HAS_AI


def provider() -> str:
    """Who answers AI calls right now: Samrudh's module, Gemini, or the saved samples."""
    return "app.ai" if _HAS_AI else "gemini" if gemini.enabled() else "samples"


# ---------------------------------------------------------------- shared data
def _fixture(name: str):
    path = FIXTURES_DIR / name
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # bad fixture shouldn't kill the server
            log.warning("could not read fixture %s: %s", name, exc)
    return None


def misconception_library() -> dict[str, dict]:
    data = _fixture("misconceptions_fractions.json") or demo_data.MISCONCEPTIONS
    return {m["id"]: m for m in data}


# ---------------------------------------------------------------- fallbacks
def _fallback_generate(topic: str, concepts_text: str, n: int, grade: str) -> list[dict]:
    bank = _fixture("questions_sample.json") or demo_data.QUESTIONS
    out = []
    for q in bank[: max(1, min(n, len(bank)))]:
        q = copy.deepcopy(q)
        for k in ("id", "assessment_id", "status"):
            q.pop(k, None)
        q["source"] = "sample"
        out.append(q)
    return out


_FRAC = r"(\d+)\s*/\s*(\d+)"


def _parse_fraction(text: str) -> Fraction | None:
    m = re.fullmatch(r"\s*" + _FRAC + r"\s*", text or "")
    if not m or int(m.group(2)) == 0:
        return None
    return Fraction(int(m.group(1)), int(m.group(2)))


def _expected_value(stem: str) -> Fraction | None:
    """Work out the correct value for simple fraction stems so we can check the answer key in code."""
    m = re.search(_FRAC + r"\s*([+\-−])\s*" + _FRAC, stem or "")
    if m:
        a, b, op, c, d = m.groups()
        if int(b) and int(d):
            x, y = Fraction(int(a), int(b)), Fraction(int(c), int(d))
            return x + y if op == "+" else x - y
    m = re.search(r"(greater|bigger|larger)\D*" + _FRAC + r"\s*or\s*" + _FRAC, stem or "", re.I)
    if m:
        _, a, b, c, d = m.groups()
        if int(b) and int(d):
            return max(Fraction(int(a), int(b)), Fraction(int(c), int(d)))
    return None


def _fallback_validate(q: dict) -> list[str]:
    errors: list[str] = []
    opts = q.get("options") or {}
    if sorted(opts.keys()) != ["A", "B", "C", "D"]:
        errors.append("Needs exactly four options A, B, C, D.")
    texts = [str(v).strip() for v in opts.values()]
    if any(not t for t in texts):
        errors.append("Every option needs text.")
    if len(set(t.lower() for t in texts)) != len(texts):
        errors.append("Two options are the same.")
    for k, v in opts.items():
        if len(str(v)) > 45:
            errors.append(f"Option {k} is too long for the sheet (max 45 characters).")
    ans = q.get("answer")
    if ans not in opts:
        errors.append("The answer must be one of A, B, C, D.")
    if not str(q.get("stem", "")).strip():
        errors.append("The question text is empty.")
    elif len(str(q["stem"]).split()) > 30:
        errors.append("Question text is too long for the sheet (max ~30 words).")
    lib = misconception_library()
    for k in opts:
        if k == ans:
            continue
        mid = ((q.get("distractors") or {}).get(k) or {}).get("misconception_id")
        if not mid:
            errors.append(f"Wrong option {k} needs a misconception tag.")
        elif mid not in lib:
            errors.append(f"Option {k} uses unknown misconception '{mid}'.")
    # maths check in code, never trust the model's answer key
    expected = _expected_value(q.get("stem", ""))
    if expected is not None and ans in opts:
        got = _parse_fraction(str(opts[ans]))
        if got is None or got != expected:
            errors.append(f"Answer key looks wrong: the correct value is {expected}.")
        for k, v in opts.items():
            if k != ans and _parse_fraction(str(v)) == expected:
                errors.append(f"Option {k} is also correct ({v}).")
    return errors


def _fallback_teaching(misconception_id: str, evidence: list[dict]) -> dict:
    m = misconception_library().get(misconception_id)
    if m and m.get("teaching_activity"):
        return {**copy.deepcopy(m["teaching_activity"]), "source": "sample"}
    return {"title": "Re-teach with a model", "minutes": 5, "source": "sample",
            "steps": ["Show the idea with a drawing or paper strip.", "Work one example together.",
                      "Ask students to explain the step in their own words."]}


# ---------------------------------------------------------------- Gemini
# Used when Samrudh's module isn't installed and AI_MODE=live, LLM_PROVIDER=gemini, LLM_API_KEY are set.
# Output goes through the same validation as everything else; anything that fails falls back to labelled samples.
_SYSTEM = ("You write short multiple-choice questions for a paper quiz in a school maths class. Students answer "
           "by filling one bubble, so keep wording short and plain. Exactly one option is correct; do the maths "
           "carefully. Every wrong option must match one specific common misconception from the list you are given, "
           "so the teacher can spot a possible misconception from the answer pattern. Never include names or "
           "personal data. Describe misconceptions as possible, never as facts about a student.")
_LETTERS = ["A", "B", "C", "D"]
_cache: dict[str, object] = {}
_cache_lock = threading.Lock()


def _cached(key: list, make):
    """Remember successful Gemini answers (insights reloads would otherwise re-ask every time)."""
    k = json.dumps(key, sort_keys=True)
    with _cache_lock:
        if k in _cache:
            return copy.deepcopy(_cache[k])
    value = make()
    with _cache_lock:
        _cache[k] = value
    return copy.deepcopy(value)


def _question_schema() -> dict:
    ids = sorted(misconception_library())
    q = {"type": "object", "required": ["concept", "stem", "options", "answer", "explanation", "distractors", "difficulty"],
         "properties": {
             "concept": {"type": "string", "description": "the idea this question checks, a few words"},
             "stem": {"type": "string", "description": "at most 25 words, fractions written like 2/3"},
             "options": {"type": "object", "required": _LETTERS,
                         "properties": {k: {"type": "string", "description": "at most 30 characters"} for k in _LETTERS}},
             "answer": {"type": "string", "enum": _LETTERS},
             "explanation": {"type": "string", "description": "one or two sentences a 12-year-old understands"},
             "distractors": {"type": "array", "description": "one entry for every WRONG option", "items": {
                 "type": "object", "required": ["option", "misconception_id", "why"],
                 "properties": {"option": {"type": "string", "enum": _LETTERS},
                                "misconception_id": {"type": "string", "enum": ids},
                                "why": {"type": "string", "description": "what a student may have done, under 10 words"}}}},
             "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]}}}
    return {"type": "object", "required": ["questions"], "properties": {"questions": {"type": "array", "items": q}}}


def _library_lines(ids: list[str] | None = None) -> str:
    lib = misconception_library()
    return "\n".join(f"- {mid}: {m.get('label', mid)}" for mid, m in lib.items() if ids is None or mid in ids)


def _from_gemini(q: dict, topic: str) -> dict:
    answer = q.get("answer")
    opts = q.get("options") if isinstance(q.get("options"), dict) else {}
    return {
        "topic": topic, "concept": str(q.get("concept", "")).strip(), "stem": str(q.get("stem", "")).strip(),
        "options": {k: str(opts.get(k, "")).strip() for k in _LETTERS}, "answer": answer,
        "explanation": str(q.get("explanation", "")).strip(),
        "distractors": {d["option"]: {"misconception_id": d.get("misconception_id"), "why": str(d.get("why", "")).strip()}
                        for d in q.get("distractors") or []
                        if isinstance(d, dict) and d.get("option") in _LETTERS and d.get("option") != answer},
        "difficulty": q.get("difficulty") if q.get("difficulty") in ("easy", "medium", "hard") else "medium",
        "source": "ai",
    }


def _gemini_questions(prompt: str, topic: str) -> tuple[list[dict], list[tuple[dict, list[str]]]]:
    """Ask Gemini; split the answer into (valid questions, [(invalid question, its errors)])."""
    raw = gemini.ask(_SYSTEM, prompt, _question_schema()).get("questions") or []
    good, bad = [], []
    for q in raw:
        q = _from_gemini(q, topic) if isinstance(q, dict) else {}
        errs = _fallback_validate(q) if q else ["Not a question."]
        (bad.append((q, errs)) if errs else good.append(q))
    return good, bad


def _gemini_generate(topic: str, concepts_text: str, n: int, grade: str) -> tuple[list[dict], str | None]:
    prompt = (f"Class grade: {grade}. Topic: {topic}.\nWhat the teacher just taught:\n{concepts_text or topic}\n\n"
              f"Write exactly {n} questions that check these ideas, easiest first. Options A-D must all differ.\n"
              f"Tag every wrong option with the misconception (from this list) that best explains choosing it:\n"
              f"{_library_lines()}")
    good, bad = _gemini_questions(prompt, topic)
    if bad and len(good) < n:  # one repair round, showing Gemini exactly what our checks said
        fix = "\n\n".join(f"Question: {json.dumps(q, ensure_ascii=False)}\nProblems: {'; '.join(e)}" for q, e in bad)
        try:
            fixed, _ = _gemini_questions("These questions failed our checks. Return corrected versions in the same "
                                         f"format, keeping the same ideas:\n\n{fix}", topic)
            good += fixed
        except gemini.GeminiError as exc:
            log.info("gemini repair failed: %s", exc.message)
    good = good[:n]
    if not good:
        raise gemini.GeminiError("bad_output", "Gemini's questions didn't pass the checks.")
    if len(good) < n:
        samples = [q for q in _fallback_generate(topic, concepts_text, n, grade)
                   if q["stem"] not in {g["stem"] for g in good}][: n - len(good)]
        return good + samples, (f"Gemini drafted {len(good)} of {n} questions. {len(samples)} saved sample "
                                f"question(s) were added because the other drafts failed the checks.")
    return good, None


def _gemini_teaching(misconception_id: str, evidence: list[dict]) -> dict:
    m = misconception_library().get(misconception_id, {})
    seen = "; ".join(f"{e.get('count')} student(s) chose option {e.get('option')}" for e in evidence) or "a repeated wrong answer"
    example = json.dumps(m.get("teaching_activity") or {}, ensure_ascii=False)
    schema = {"type": "object", "required": ["title", "minutes", "steps"], "properties": {
        "title": {"type": "string", "description": "under 8 words"},
        "minutes": {"type": "integer", "minimum": 3, "maximum": 10},
        "steps": {"type": "array", "minItems": 2, "maxItems": 4, "items": {"type": "string", "description": "one short sentence"}}}}
    out = gemini.ask(
        "You help a school maths teacher plan a quick whole-class activity. Use paper strips, drawings or a number "
        "line so students test the idea themselves. Plain words, no student names, no labels like 'weak'.",
        f"Possible misconception in the class: {m.get('label', misconception_id)}.\n"
        f"What it may look like to a student: {m.get('student_friendly', '')}\n"
        f"Evidence from the quiz: {seen}.\nAn activity the team already uses, for style: {example}\n"
        "Suggest one different 5-minute activity with 3 short steps.", schema, temperature=0.6)
    steps = [str(s).strip() for s in out.get("steps") or [] if str(s).strip()]
    title = str(out.get("title", "")).strip()
    minutes = out.get("minutes")
    if not title or not 2 <= len(steps) <= 5 or not isinstance(minutes, int) or not 1 <= minutes <= 15 \
            or any(len(s) > 220 for s in steps):
        raise gemini.GeminiError("bad_output", "Gemini's activity didn't pass the checks.")
    return {"title": title[:80], "minutes": minutes, "steps": steps, "source": "ai"}


def _gemini_followups(misconception_ids: list[str], n: int) -> list[dict]:
    prompt = (f"Write exactly {n} new question(s) to check, after reteaching, whether these possible "
              f"misconceptions remain:\n{_library_lines(misconception_ids)}\n"
              "For each question, one wrong option must match the targeted misconception; tag every wrong option "
              f"with the best misconception from this full list:\n{_library_lines()}")
    good, _ = _gemini_questions(prompt, "fractions")
    if not good:
        raise gemini.GeminiError("bad_output", "Gemini's follow-up questions didn't pass the checks.")
    return good[:n]


def _fallback_followups(misconception_ids: list[str], n: int) -> list[dict]:
    out, seen = [], set()
    for mid in misconception_ids:
        q = demo_data.FOLLOWUPS.get(mid)
        if q and q["stem"] not in seen:
            seen.add(q["stem"])
            q = copy.deepcopy(q)
            q["source"] = "sample"
            out.append(q)
        if len(out) >= n:
            break
    if not out:
        q = copy.deepcopy(demo_data.FOLLOWUPS["M_ADD_DENOMS"])
        q["source"] = "sample"
        out.append(q)
    return out


# ---------------------------------------------------------------- public API
def generate_questions(topic: str, concepts_text: str, n: int, grade: str) -> tuple[list[dict], str | None]:
    """Returns (questions, note). note is set when we had to fall back."""
    if _HAS_AI:
        try:
            qs = _ai.generate_questions(topic=topic, concepts_text=concepts_text, n=n, grade=grade)
            if qs:
                note = "Using saved sample questions (AI unavailable)" if all(q.get("source") == "sample" for q in qs) else None
                return qs, note
        except Exception as exc:
            log.warning("ai.generate_questions failed, using samples: %s", exc)
    elif gemini.enabled():
        try:
            return _gemini_generate(topic, concepts_text, n, grade)
        except gemini.GeminiError as exc:
            log.warning("gemini generate failed (%s): %s", exc.kind, exc.message)
            return _fallback_generate(topic, concepts_text, n, grade), f"{exc.message} Using saved sample questions."
    return _fallback_generate(topic, concepts_text, n, grade), "Using saved sample questions (AI unavailable)"


def validate_question(q: dict) -> list[str]:
    errors = _fallback_validate(q)  # always run our structural + maths checks
    if _HAS_AI:
        try:
            for e in _ai.validate_question(q) or []:
                if e not in errors:
                    errors.append(e)
        except Exception as exc:
            log.warning("ai.validate_question failed: %s", exc)
    return errors


def teaching_suggestion(misconception_id: str, evidence: list[dict]) -> dict:
    if _HAS_AI:
        try:
            s = _ai.teaching_suggestion(misconception_id=misconception_id, evidence=evidence)
            if s and s.get("steps"):
                return s
        except Exception as exc:
            log.warning("ai.teaching_suggestion failed: %s", exc)
    elif gemini.enabled():
        try:
            return _cached(["teach", misconception_id, evidence], lambda: _gemini_teaching(misconception_id, evidence))
        except gemini.GeminiError as exc:
            log.warning("gemini teaching failed (%s): %s", exc.kind, exc.message)
    return _fallback_teaching(misconception_id, evidence)


def followup_questions(misconception_ids: list[str], n: int) -> list[dict]:
    if _HAS_AI:
        try:
            qs = _ai.followup_questions(misconception_ids=misconception_ids, n=n)
            good = [q for q in qs or [] if not _fallback_validate(q)]
            if good:
                return good[:n]
        except Exception as exc:
            log.warning("ai.followup_questions failed: %s", exc)
    elif gemini.enabled():
        try:
            return _cached(["followup", sorted(misconception_ids), n], lambda: _gemini_followups(misconception_ids, n))
        except gemini.GeminiError as exc:
            log.warning("gemini followups failed (%s): %s", exc.kind, exc.message)
    return _fallback_followups(misconception_ids, n)
