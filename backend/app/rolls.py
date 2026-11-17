"""Roll numbers: what a student writes at the top of the paper. Always strings ("01", "12B"), never ints.

Matching only ever looks at ONE class's roster (the selected assessment's class), so two classes can share "01".
"""
import re


def from_student_code(code: str) -> str:
    """Backfill for existing rosters: "7A-01" -> "01"."""
    return code.rsplit("-", 1)[-1].strip() if "-" in code else code.strip()


def normalize(text) -> str:
    """Spacing, separators and case don't matter on paper: " 0 7 " == "07", "12-b" == "12B"."""
    return re.sub(r"[\s\-_./#:]", "", str(text or "")).upper()


def _loose(n: str) -> str:
    return re.sub(r"^0+(?=\d)", "", n)  # "007" -> "7", "07B" -> "7B", "0" stays "0"


def match(written, roster) -> dict:
    """roster: Student rows of the assessment's class. Never guesses between several students.

    Returns {"status": matched|ambiguous|unknown|unreadable, "student_id"?, "candidates": [ids], "exact"?}.
    An exact match (after normalizing) wins; otherwise "7" may match "07" if that is the only possibility.
    """
    w = normalize(written)
    if not w:
        return {"status": "unreadable", "candidates": []}
    exact = [s for s in roster if w in (normalize(s.roll_no), normalize(s.student_code))]
    pool = exact or [s for s in roster if s.roll_no and _loose(w) == _loose(normalize(s.roll_no))]
    if len(pool) == 1:
        return {"status": "matched", "student_id": pool[0].id, "candidates": [pool[0].id], "exact": bool(exact)}
    if len(pool) > 1:
        return {"status": "ambiguous", "candidates": sorted(s.id for s in pool)}
    return {"status": "unknown", "candidates": []}
