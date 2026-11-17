"""Photo -> upright, flattened page -> bubble states. Pure image work, no database.

Identity no longer comes from the image here (no QR): Gemini reads the handwritten roll number and the roster
match happens in the scan route. This module keeps the deterministic bubble reader, used to cross-check Gemini
and as the fallback when Gemini is unavailable.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.layout import base
from app.scanner import align, omr


def decode_image(data: bytes) -> np.ndarray | None:
    """Decode upload, honouring the phone's EXIF rotation."""
    try:
        from PIL import Image, ImageOps
        import io
        pil = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    except Exception:
        img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    if max(h, w) > 3000:  # phone photos can be huge; this is plenty
        s = 3000 / max(h, w)
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return img


def _roll_box_ink(page: np.ndarray) -> float:
    """How dark the printed roll-number box borders are where they should be on an upright page."""
    L, k = base(), base()["px_per_mm"]
    rb = L["roll_box"]
    gray = page.min(axis=2) if page.ndim == 3 else page
    y0, y1 = int((rb["y"] + 2) * k), int((rb["y"] + rb["h"] - 2) * k)
    vals = []
    for i in range(rb["count"] + 1):
        x = int((rb["x"] + i * rb["w"]) * k)
        strip = gray[y0:y1, max(x - 4, 0):x + 5]
        if strip.size:
            vals.append(float(255 - strip.min(axis=1).mean()) / 255)
    return float(np.mean(vals)) if vals else 0.0


def upright(page: np.ndarray) -> np.ndarray:
    """The four corner markers look the same both ways up; the thick roll-number boxes at the top don't."""
    flipped = cv2.rotate(page, cv2.ROTATE_180)
    return flipped if _roll_box_ink(flipped) > max(_roll_box_ink(page) * 1.5, 0.25) else page


def locate(img: np.ndarray) -> tuple[np.ndarray | None, str | None]:
    """Returns (flat upright page, None) or (None, reason: too_dark | too_blurry | page_not_found)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    quad = align.find_page(gray)
    if quad is None:  # sideways photo? try both quarter turns
        for rot in (cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE):
            r_img = cv2.rotate(img, rot)
            quad = align.find_page(cv2.cvtColor(r_img, cv2.COLOR_BGR2GRAY))
            if quad is not None:
                img = r_img
                break
    if quad is None:
        return None, align.quality_reason(gray)
    return upright(align.warp_page(img, quad)), None


def read_answers(page: np.ndarray, n_questions: int) -> list[dict]:
    out = []
    for fills in omr.bubble_fills(page, n_questions):
        res = omr.classify(fills)
        res["fill"] = fills
        out.append(res)
    return out
