"""Make fake 'phone photos' of filled sheets so the scanner can be tested without a printer.
Real printed sheets are still the real test (see demo/scan_log.md)."""
from __future__ import annotations

import cv2
import numpy as np
import pypdfium2 as pdfium

from app.layout import base, question_blocks


def render_pages(pdf_bytes: bytes, dpi: int = 150) -> list[np.ndarray]:
    doc = pdfium.PdfDocument(pdf_bytes)
    pages = []
    for i in range(len(doc)):
        pil = doc[i].render(scale=dpi / 72).to_pil().convert("RGB")
        pages.append(cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR))
    return pages


def fill(page: np.ndarray, n_questions: int, marks: list, ink=(60, 40, 30), strength=1.0) -> np.ndarray:
    """marks[i] = 'A' | 'AB' (double) | '' (blank) | 'a' (faint/half mark)."""
    img = page.copy()
    h, w = img.shape[:2]
    kx, ky = w / base()["page_mm"][0], h / base()["page_mm"][1]
    r = base()["bubble_radius_mm"]
    for block, m in zip(question_blocks(n_questions), marks):
        for ch in m:
            bx, by = block["bubbles"][ch.upper()]
            centre = (int(bx * kx), int(by * ky))
            if ch.islower():  # faint, partial scribble
                cv2.circle(img, centre, int(r * 0.5 * kx), (150, 150, 150), -1)
            else:
                rr = int(r * 0.85 * kx)
                cv2.circle(img, centre, rr, tuple(int(c + (255 - c) * (1 - strength)) for c in ink), -1)
    return img


def photograph(page: np.ndarray, *, angle=8, persp=0.06, brightness=1.0, blur=1, upside_down=False, seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if upside_down:
        page = cv2.rotate(page, cv2.ROTATE_180)
    h, w = page.shape[:2]
    canvas_w, canvas_h = int(w * 1.5), int(h * 1.4)
    bg = np.full((canvas_h, canvas_w, 3), (90, 110, 120), np.uint8)  # desk
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    j = lambda: rng.uniform(-persp, persp)
    ox, oy = (canvas_w - w) / 2, (canvas_h - h) / 2
    dst = np.float32([[ox + w * j(), oy + h * j()], [ox + w * (1 + j()), oy + h * j()],
                      [ox + w * (1 + j()), oy + h * (1 + j())], [ox + w * j(), oy + h * (1 + j())]])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(page, M, (canvas_w, canvas_h), borderMode=cv2.BORDER_TRANSPARENT, dst=bg)
    R = cv2.getRotationMatrix2D((canvas_w / 2, canvas_h / 2), angle, 1.0)
    out = cv2.warpAffine(warped, R, (canvas_w, canvas_h), borderValue=(90, 110, 120))
    # uneven lighting gradient + noise
    grad = np.linspace(0.8, 1.05, canvas_w, dtype=np.float32)[None, :, None]
    out = np.clip(out.astype(np.float32) * grad * brightness + rng.normal(0, 4, out.shape), 0, 255).astype(np.uint8)
    if blur:
        out = cv2.GaussianBlur(out, (2 * blur + 1, 2 * blur + 1), 0)
    return out


def jpeg(img: np.ndarray, quality=85) -> bytes:
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()
