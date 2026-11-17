"""Read bubble marks at the fixed layout positions on a flattened page."""
from __future__ import annotations

import cv2
import numpy as np

from app import config
from app.layout import base, question_blocks


def _ink(page_bgr: np.ndarray) -> np.ndarray:
    # min over colour channels: blue/black pen and pencil all come out dark
    return page_bgr.min(axis=2) if page_bgr.ndim == 3 else page_bgr


def bubble_fills(page_bgr: np.ndarray, n_questions: int) -> list[dict[str, float]]:
    L = base()
    k = L["px_per_mm"]
    r = L["bubble_radius_mm"] * k
    gray = _ink(page_bgr).astype(np.float32)
    inner = int(r * 0.68)
    yy, xx = np.mgrid[-inner:inner + 1, -inner:inner + 1]
    disc = (xx ** 2 + yy ** 2) <= inner ** 2
    win = int(r * 1.35)
    out = []
    for block in question_blocks(n_questions):
        fills = {}
        for opt, (bx, by) in block["bubbles"].items():
            cx, cy = int(bx * k), int(by * k)
            area = gray[cy - win:cy + win + 1, cx - win:cx + win + 1]
            bg = float(np.percentile(area, 92)) if area.size else 255.0
            bg = max(bg, 60.0)
            patch = gray[cy - inner:cy + inner + 1, cx - inner:cx + inner + 1]
            if patch.shape != disc.shape:
                fills[opt] = 0.0
                continue
            dark = patch[disc] < bg * 0.62
            fills[opt] = round(float(dark.mean()), 3)
        out.append(fills)
    return out


def classify(fills: dict[str, float]) -> dict:
    """single | blank | multiple | ambiguous, plus detected option and confidence."""
    filled_t, empty_t = config.OMR_FILLED, config.OMR_EMPTY
    ranked = sorted(fills.items(), key=lambda kv: kv[1], reverse=True)
    (top_opt, top), (_, second) = ranked[0], ranked[1]
    marked = [o for o, v in ranked if v >= filled_t]
    if len(marked) >= 2:
        return {"state": "multiple", "detected": None, "confidence": 0.0}
    if not marked:
        if top < empty_t:
            return {"state": "blank", "detected": None, "confidence": round(1 - top / empty_t, 2)}
        return {"state": "ambiguous", "detected": top_opt, "confidence": 0.3}
    if second >= empty_t:  # e.g. an erased mark next to a filled one
        return {"state": "ambiguous", "detected": top_opt, "confidence": 0.5}
    conf = min(1.0, 0.6 + (top - second))
    return {"state": "single", "detected": top_opt, "confidence": round(conf, 2)}


def crops(page_bgr: np.ndarray, n_questions: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """(bubble row, reasoning box) image crops per question, kept as evidence."""
    k = base()["px_per_mm"]
    out = []
    for block in question_blocks(n_questions):
        by = list(block["bubbles"].values())[0][1]
        row = page_bgr[int((by - 7) * k):int((by + 7) * k), int(14 * k):int(196 * k)]
        x0, y0, x1, y1 = block["why_box"]
        why = page_bgr[int(y0 * k):int(y1 * k), int(x0 * k):int(x1 * k)]
        out.append((row, why))
    return out
