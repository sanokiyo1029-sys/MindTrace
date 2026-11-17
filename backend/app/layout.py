"""Computes where everything sits on a sheet. Used by BOTH pdf.py and scanner/omr.py."""
import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).with_name("sheet_layout.json")


@lru_cache
def base() -> dict:
    return json.loads(_PATH.read_text())


def paper_code(assessment_id: str) -> str:
    """Short code printed on every copy so a scan can be checked against the selected assessment."""
    return assessment_id.split("_", 1)[-1].upper()


def question_blocks(n: int) -> list[dict]:
    """Per question: stem position, bubble centres (mm) and the reasoning box (mm)."""
    L = base()
    n = max(1, min(n, L["max_questions"]))
    top, bottom = L["questions_top_mm"], L["questions_bottom_mm"]
    h = (bottom - top) / n
    blocks = []
    for i in range(n):
        y0 = top + i * h
        stem_y = y0 + 6
        bubble_y = y0 + min(20, h * 0.36)
        why_top = bubble_y + 10  # leaves room for 2-3 lines of option text
        why_bottom = y0 + h - 4
        blocks.append({
            "index": i,
            "y0": y0,
            "height": h,
            "stem_xy": (20, stem_y),
            "bubbles": {opt: (x, bubble_y) for opt, x in zip("ABCD", L["bubble_option_x_mm"])},
            "why_box": (20, why_top, 190, max(why_bottom, why_top + 8)),  # x0, y0, x1, y1
        })
    return blocks
