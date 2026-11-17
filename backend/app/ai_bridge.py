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
from fractions import Fraction

from app import demo_data
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
        return copy.deepcopy(m["teaching_activity"])
    return {"title": "Re-teach with a model", "minutes": 5,
            "steps": ["Show the idea with a drawing or paper strip.", "Work one example together.",
                      "Ask students to explain the step in their own words."]}


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
    return _fallback_followups(misconception_ids, n)
