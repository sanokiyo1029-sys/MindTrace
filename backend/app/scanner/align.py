"""Find the 4 solid corner squares and warp the photo to a flat, fixed-size page."""
from __future__ import annotations

import cv2
import numpy as np

from app.layout import base


def page_size_px() -> tuple[int, int]:
    L = base()
    return int(L["page_mm"][0] * L["px_per_mm"]), int(L["page_mm"][1] * L["px_per_mm"])


def _candidates(gray: np.ndarray) -> list[tuple[float, float, float]]:
    """Solid, square-ish dark blobs: (cx, cy, area)."""
    h, w = gray.shape
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    min_area = (h * w) * 0.00004
    out = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        rect = cv2.minAreaRect(c)
        (cx, cy), (rw, rh), _ = rect
        if rw == 0 or rh == 0:
            continue
        aspect = min(rw, rh) / max(rw, rh)
        rectangularity = area / (rw * rh)
        if aspect < 0.6 or rectangularity < 0.8:
            continue
        # solidity of the filled region (QR finder patterns are rings, so they fail this)
        mask = np.zeros_like(bw)
        cv2.drawContours(mask, [c], -1, 255, -1)
        filled = cv2.countNonZero(cv2.bitwise_and(bw, mask)) / max(cv2.countNonZero(mask), 1)
        if filled < 0.85:
            continue
        out.append((cx, cy, area))
    return out


def find_page(gray: np.ndarray) -> np.ndarray | None:
    """Returns the 4 marker centres in image px ordered tl, tr, br, bl, or None."""
    cands = _candidates(gray)
    if len(cands) < 4:
        return None
    # markers are the biggest solid squares; keep the top few by area and pick extremes
    cands.sort(key=lambda t: t[2], reverse=True)
    top = cands[:10]
    big = top[0][2]
    top = [c for c in top if c[2] > big * 0.25]
    if len(top) < 4:
        return None
    pts = np.array([[c[0], c[1]] for c in top], dtype=np.float32)
    s, d = pts.sum(axis=1), pts[:, 0] - pts[:, 1]
    tl, br = pts[np.argmin(s)], pts[np.argmax(s)]
    tr, bl = pts[np.argmax(d)], pts[np.argmin(d)]
    quad = np.array([tl, tr, br, bl], dtype=np.float32)
    if len({tuple(p) for p in quad.tolist()}) < 4:
        return None
    # sanity: the quad should look like the marker rectangle (ratio 180 x 267 mm)
    width = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    height = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    if width < 1 or not (0.45 < width / height < 1.0):
        return None
    return quad


def warp_page(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
    L = base()
    k = L["px_per_mm"]
    m = L["marker_centres_mm"]
    dst = np.array([m["tl"], m["tr"], m["br"], m["bl"]], dtype=np.float32) * k
    M = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img, M, page_size_px(), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))


def quality_reason(gray: np.ndarray) -> str:
    """Best guess at why a page wasn't found, for the retry prompt."""
    if float(gray.mean()) < 70:
        return "too_dark"
    small = cv2.resize(gray, (800, int(800 * gray.shape[0] / gray.shape[1])))
    if cv2.Laplacian(small, cv2.CV_64F).var() < 25:
        return "too_blurry"
    return "page_not_found"
