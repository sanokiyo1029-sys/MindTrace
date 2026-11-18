"""Question types and marking (CONTRACTS: "Question types and marking").

Every question is a dict with `type` (missing = "mcq") and `marks` (missing = 1). This module knows, per type:
  - validate(q)      -> list of problems a teacher must fix before approving
  - paper_kind(q)    -> "mcq" (bubbles on the printed sheet) or "descriptive" (a written-answer box)
  - mark(q, resp)    -> score (partial credit where it makes sense), or None when a teacher has to mark it
Responses can be structured (online exams) or the text read from a paper / typed by the teacher.
Student code is never run: programming answers are always teacher-marked."""
import hashlib
import re
from fractions import Fraction

TYPES = {
    "mcq": "Multiple choice", "multi_select": "Multiple select", "true_false": "True / False",
    "fill_blank": "Fill in the blanks", "match": "Match the following", "assertion_reason": "Assertion and reason",
    "one_word": "One-word answer", "short": "Short answer", "long": "Long answer", "essay": "Essay",
    "maths": "Mathematical problem", "numerical": "Numerical problem", "diagram": "Diagram-based",
    "image": "Image-based", "programming": "Programming", "code": "Code-based", "graph": "Graph interpretation",
    "descriptive": "Written answer",  # the original written type, kept for older papers
}
MANUAL = {"short", "long", "essay", "programming", "descriptive"}   # always teacher-marked
FLEX = {"maths", "diagram", "image", "code", "graph"}               # auto-marked only when they carry an answer key
TRUE_FALSE = {"A": "True", "B": "False"}
ASSERTION_REASON = {
    "A": "Both true; R explains A",
    "B": "Both true; R doesn't explain A",
    "C": "A true, R false",
    "D": "A false, R true",
}
# Everything a teacher may set on a question (besides the original MCQ fields).
FIELDS = {"type", "stem", "concept", "marks", "options", "answer", "answers", "blanks", "pairs", "accepted", "value",
          "tolerance", "unit", "code", "image_url", "model_answer", "look_for", "explanation", "distractors",
          "difficulty", "rubric"}
LETTERS = "ABCD"


def qtype(q: dict) -> str:
    return q.get("type") or "mcq"


def marks(q: dict) -> float:
    try:
        return float(q.get("marks", 1))
    except (TypeError, ValueError):
        return 1.0


def style(q: dict) -> str:
    """How the answer is checked: choice | multi | blanks | match | words | number | manual."""
    t = qtype(q)
    if t in ("mcq", "true_false", "assertion_reason"):
        return "choice"
    if t == "multi_select":
        return "multi"
    if t == "fill_blank":
        return "blanks"
    if t == "match":
        return "match"
    if t == "one_word":
        return "words"
    if t == "numerical":
        return "number"
    if t in FLEX:  # the teacher picked how it's marked; a half-filled key fails validation instead of going manual
        if q.get("options"):
            return "choice"
        if q.get("value") is not None:
            return "number"
        if q.get("accepted") is not None:
            return "words"
    return "manual"


def paper_kind(q: dict) -> str:
    """One bubble per question on paper, or a written-answer box (where the student writes letters, words, numbers,
    working, a diagram or code). The printed layout, the bubble reader and the review screen all go by this."""
    return "mcq" if style(q) == "choice" else "descriptive"


def written(q: dict) -> bool:
    return paper_kind(q) == "descriptive"


def options(q: dict) -> dict:
    t = qtype(q)
    return TRUE_FALSE if t == "true_false" else ASSERTION_REASON if t == "assertion_reason" else (q.get("options") or {})


def match_choices(q: dict) -> list[str]:
    """Right-hand column in a fixed shuffled order (the same on paper and online), labelled A, B, C ..."""
    rights = [str(p[1]) for p in q.get("pairs") or []]
    seed = str(q.get("stem", ""))  # not the id: stored question data has none, and paper + online must agree
    return sorted(rights, key=lambda r: hashlib.sha256(f"{seed}|{r}".encode()).hexdigest())


def paper_lines(q: dict) -> list[str]:
    """Extra lines printed under the question for types whose choices don't fit bubbles."""
    s, t = style(q), qtype(q)
    if t == "multi_select":
        return ["  ".join(f"{k}) {v}" for k, v in options(q).items()), "Write ALL the correct letters."]
    if s == "match":
        left = "  ".join(f"{i + 1}. {p[0]}" for i, p in enumerate(q.get("pairs") or []))
        right = "  ".join(f"{LETTERS_EXT[i]}. {r}" for i, r in enumerate(match_choices(q)))
        return [left, right, "Write pairs like 1-B, 2-A."]
    if s == "blanks":
        return [f"Write the {len(q.get('blanks') or [])} missing words in order, one per line."]
    if s == "number":
        return ["Show your working. Write the final answer" + (f" in {q['unit']}." if q.get("unit") else ".")]
    return []


LETTERS_EXT = "ABCDEFGHIJ"


# ---------------------------------------------------------------- validation
def validate(q: dict) -> list[str]:
    """Structural checks for every type except plain MCQ (ai_bridge keeps its MCQ + misconception checks)."""
    t, errs = qtype(q), []
    if t not in TYPES:
        return [f"Unknown question type '{t}'."]
    if not str(q.get("stem", "")).strip():
        errs.append("The question text is empty.")
    elif len(str(q["stem"]).split()) > 60:
        errs.append("Question text is too long for the sheet (max ~60 words).")
    m = q.get("marks", 1)
    if not isinstance(m, (int, float)) or isinstance(m, bool) or not 0.5 <= m <= 20:
        errs.append("Marks must be a number from 0.5 to 20.")
    if len(str(q.get("model_answer") or "")) > 1500:
        errs.append("Keep the model answer under 1500 characters.")
    if len(str(q.get("code") or "")) > 1200:
        errs.append("Keep the code under 1200 characters.")
    s = style(q)
    opts = options(q)
    if s in ("choice", "multi") and t not in ("true_false", "assertion_reason"):
        keys = list(opts)
        if not 2 <= len(keys) <= 4 or keys != list(LETTERS[:len(keys)]):
            errs.append("Needs 2 to 4 options labelled A, B, C, D in order.")
        texts = [str(v).strip() for v in opts.values()]
        if any(not x for x in texts):
            errs.append("Every option needs text.")
        elif len({x.lower() for x in texts}) != len(texts):
            errs.append("Two options are the same.")
        if any(len(x) > 60 for x in texts):
            errs.append("Keep each option under 60 characters.")
    if s == "choice" and q.get("answer") not in opts:
        errs.append("Choose the correct option.")
    if s == "multi":
        ans = q.get("answers") or []
        if not ans or any(a not in opts for a in ans) or len(set(ans)) != len(ans):
            errs.append("Tick at least one correct option.")
    if s == "blanks":
        blanks = q.get("blanks") or []
        if not blanks or any(not [w for w in b if str(w).strip()] for b in blanks):
            errs.append("Give the accepted answer(s) for every blank.")
        elif str(q.get("stem", "")).count("___") not in (0, len(blanks)):
            errs.append("The number of ___ gaps in the question doesn't match the answers.")
    if s == "match":
        pairs = q.get("pairs") or []
        if not 2 <= len(pairs) <= 6 or any(len(p) != 2 or not str(p[0]).strip() or not str(p[1]).strip() for p in pairs):
            errs.append("Give 2 to 6 complete pairs.")
        elif len({str(p[1]).strip().lower() for p in pairs}) != len(pairs):
            errs.append("Each right-hand item must be different.")
    if s == "words" and not [w for w in q.get("accepted") or [] if str(w).strip()]:
        errs.append("Give at least one accepted answer.")
    if s == "number":
        if number(q.get("value")) is None:
            errs.append("Give the correct numerical answer.")
        tol = q.get("tolerance", 0) or 0
        if number(tol) is None or number(tol) < 0:
            errs.append("Tolerance must be zero or a positive number.")
    return errs


# ---------------------------------------------------------------- marking
def norm(s) -> str:
    """Case, spacing and trailing punctuation don't matter: ' Photo-Synthesis. ' == 'photo-synthesis'."""
    return re.sub(r"\s+", " ", str(s or "")).strip().strip(".!").lower()


_NUM = re.compile(r"[-−]?\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?(?:[eE][-+]?\d+)?")


def number(s) -> Fraction | None:
    """First number in the text: 12, -3.5, 3/4, 6.02e23 (commas as thousands separators are ignored)."""
    try:
        if isinstance(s, (int, float)) and not isinstance(s, bool):
            return Fraction(str(s))
        m = _NUM.search(str(s or "").replace(",", "").replace("−", "-"))
        if not m:
            return None
        txt = m.group(0).replace(" ", "")
        if "/" in txt:
            a, b = txt.split("/")
            return Fraction(Fraction(a), Fraction(b)) if Fraction(b) else None
        return Fraction(txt) if "e" not in txt.lower() else Fraction(float(txt))
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def parse(q: dict, text: str):
    """Turn what a student wrote on paper (or typed) into the structured response for the type."""
    s = style(q)
    if s == "multi":
        return sorted(set(re.findall(r"\b([A-D])\b", str(text).upper())))
    if s == "match":
        return {int(i): c for i, c in re.findall(r"(\d+)\s*[-–:=>.)]*\s*([A-J])\b", str(text).upper())}
    if s == "blanks":
        parts = [p for p in re.split(r"[\n;|]+", str(text)) if p.strip()]
        if len(parts) == 1 and len(q.get("blanks") or []) > 1:
            parts = [p for p in parts[0].split(",") if p.strip()]
        return parts
    if s == "choice":
        m = re.search(r"\b([A-D])\b", str(text).upper())
        return m.group(1) if m else None
    return text


def mark(q: dict, response) -> float | None:
    """Score out of marks(q), or None when a teacher has to mark it. Text responses are parsed first."""
    s, full = style(q), marks(q)
    if s == "manual":
        return None
    if isinstance(response, str) and s not in ("words", "number"):
        response = parse(q, response)
    if response in (None, "", [], {}):
        return 0.0
    if s == "choice":
        frac = 1.0 if str(response).strip().upper() == q.get("answer") else 0.0
    elif s == "multi":
        right, picked = set(q.get("answers") or []), {str(x).upper() for x in response}
        frac = max(0, len(picked & right) - len(picked - right)) / len(right)  # a wrong tick cancels a right one
    elif s == "blanks":
        blanks = q.get("blanks") or []
        given = list(response) + [""] * len(blanks)
        frac = sum(norm(g) in {norm(w) for w in b} for g, b in zip(given, blanks)) / len(blanks)
    elif s == "match":
        pairs, labels = q.get("pairs") or [], match_choices(q)
        got = {int(k): v for k, v in dict(response).items()}
        right = 0
        for i, p in enumerate(pairs, start=1):
            v = str(got.get(i, ""))
            v = labels[LETTERS_EXT.index(v)] if len(v) == 1 and v in LETTERS_EXT[:len(labels)] else v
            right += norm(v) == norm(p[1])
        frac = right / len(pairs)
    elif s == "words":
        frac = 1.0 if norm(response) in {norm(w) for w in q.get("accepted") or []} else 0.0
    else:  # number
        got, want, tol = number(response), number(q.get("value")), number(q.get("tolerance") or 0) or 0
        frac = 1.0 if got is not None and want is not None and abs(got - want) <= tol else 0.0
    return round(full * frac, 2)


def answer_score(q: dict, ans: dict | None) -> float | None:
    """Score for one scanned/online answer: a teacher's mark wins; otherwise auto-mark what was read.
    None = not marked yet (needs the teacher, or the handwriting hasn't been read)."""
    if not ans:
        return None
    if ans.get("teacher_score") is not None:
        return float(ans["teacher_score"])
    final = ans.get("final")
    if final is None:
        return None
    if final == "blank":
        return 0.0
    if paper_kind(q) == "mcq":
        return mark(q, final)
    if ans.get("text_state") not in ("clear", "teacher") and "response" not in ans:
        return None  # nothing reliable to mark yet
    return mark(q, ans.get("response", ans.get("text", "")))


def scored(q: dict, ans: dict) -> dict:
    """The answer plus score, max_score and scored_by (teacher | auto | None = still to mark), for API output."""
    s = answer_score(q, ans)
    by = "teacher" if ans.get("teacher_score") is not None else (None if s is None else "auto")
    return {**ans, "score": s, "max_score": marks(q), "scored_by": by}


def totals(qs: dict, answers: list[dict]) -> dict:
    """Paper total over every question: {score, max_score, to_mark}. Unmarked answers count 0 until marked."""
    got = {x["question_id"]: x for x in answers}
    score = to_mark = 0.0
    for qid, q in qs.items():
        s = answer_score(q, got.get(qid))
        if s is None and got.get(qid, {}).get("final") is not None:
            to_mark += 1
        score += s or 0
    return {"score": round(score, 2), "max_score": round(sum(marks(q) for q in qs.values()), 2), "to_mark": int(to_mark)}
