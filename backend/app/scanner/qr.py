from __future__ import annotations

import cv2
import numpy as np

from app.layout import base

_detector = cv2.QRCodeDetector()
PREFIX = "MT:"


def _decode(img: np.ndarray) -> tuple[str | None, np.ndarray | None]:
    try:
        text, points, _ = _detector.detectAndDecode(img)
    except cv2.error:
        return None, None
    if text and text.startswith(PREFIX):
        return text[len(PREFIX):].strip(), points
    return None, None


def read_qr_box(page: np.ndarray) -> str | None:
    """Decode only the expected QR area of a flattened page (so we also learn orientation)."""
    L = base()
    k = L["px_per_mm"]
    q = L["qr"]
    pad = 8
    x0, y0 = int((q["x"] - pad) * k), int((q["y"] - pad) * k)
    x1, y1 = int((q["x"] + q["size"] + pad) * k), int((q["y"] + q["size"] + pad) * k)
    crop = page[max(0, y0):y1, max(0, x0):x1]
    for candidate in (crop, cv2.resize(crop, None, fx=0.5, fy=0.5)):
        sid, _ = _decode(candidate)
        if sid:
            return sid
    return None


def read_anywhere(img: np.ndarray) -> tuple[str | None, tuple[float, float] | None]:
    """Decode anywhere in an image. Returns (sheet_id, QR centre as fraction of width/height)."""
    h, w = img.shape[:2]
    scale = 1.0
    if max(h, w) > 1600:
        scale = 1600 / max(h, w)
    for im, s in ((img, 1.0), (cv2.resize(img, None, fx=scale, fy=scale), scale)):
        sid, pts = _decode(im)
        if sid:
            centre = None
            if pts is not None:
                c = np.asarray(pts).reshape(-1, 2).mean(axis=0) / s
                centre = (float(c[0] / w), float(c[1] / h))
            return sid, centre
        if s == 1.0 and scale == 1.0:
            break
    return None, None
