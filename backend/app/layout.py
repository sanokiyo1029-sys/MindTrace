"""Computes where everything sits on a sheet. Used by BOTH pdf.py and scanner/omr.py."""
import json
from functools import lru_cache
from pathlib import Path

from app import marking

_PATH = Path(__file__).with_name("sheet_layout.json")


@lru_cache
def base() -> dict:
    return json.loads(_PATH.read_text())


def paper_code(assessment_id: str) -> str:
    """Short code printed on every copy so a scan can be checked against the selected assessment."""
    return assessment_id.split("_", 1)[-1].upper()


DESCRIPTIVE_WEIGHT = 1.6  # a written-answer block gets more room than a bubble question
PICTURE_WEIGHT = 2.2      # a bubble question with a picture: the picture sits in its (taller) Why box


def question_blocks(n: int, types: list[str] | None = None) -> list[dict]:
    """Per question: stem position, bubble centres (mm) and the reasoning / written-answer box (mm).
    types[i] is "mcq" (default), "mcq_picture" (bubbles + room for a picture) or "descriptive" (no bubbles, one big
    answer box). A plain bubble question never gets less room than on an all-bubble paper, so its text and bubbles
    don't collide when a paper has several written answers; the written boxes share what's left."""
    L = base()
    n = max(1, min(n, L["max_questions"]))
    types = [(types[i] if types and i < len(types) else "mcq") for i in range(n)]
    top, bottom = L["questions_top_mm"], L["questions_bottom_mm"]
    weights = [{"mcq": 1.0, "mcq_picture": PICTURE_WEIGHT}.get(t, DESCRIPTIVE_WEIGHT) for t in types]
    area, min_bubble = bottom - top, (bottom - top) / L["max_questions"]
    heights = [area * w / sum(weights) for w in weights]
    n_plain = types.count("mcq")
    if 0 < n_plain < n and heights[types.index("mcq")] < min_bubble:
        rest = sum(w for t, w in zip(types, weights) if t != "mcq")
        heights = [min_bubble if t == "mcq" else (area - min_bubble * n_plain) * w / rest for t, w in zip(types, weights)]
    blocks, y0 = [], top
    for i, (t, h) in enumerate(zip(types, heights)):
        stem_y = y0 + 6
        if t == "descriptive":
            bubbles, why_top = {}, y0 + 14  # room for a two-line question
        else:
            bubble_y = y0 + min(20, h * 0.36)
            bubbles = {opt: (x, bubble_y) for opt, x in zip("ABCD", L["bubble_option_x_mm"])}
            why_top = bubble_y + 10  # leaves room for 2-3 lines of option text
        why_bottom = y0 + h - 4
        blocks.append({
            "index": i, "type": t, "y0": y0, "height": h, "stem_xy": (20, stem_y), "bubbles": bubbles,
            "why_box": (20, why_top, 190, max(why_bottom, why_top + 8)),  # x0, y0, x1, y1
        })
        y0 += h
    return blocks


def question_types(questions: list[dict]) -> list[str]:
    return [("mcq_picture" if q.get("image_url") else "mcq") if marking.paper_kind(q) == "mcq" else "descriptive"
            for q in questions]
