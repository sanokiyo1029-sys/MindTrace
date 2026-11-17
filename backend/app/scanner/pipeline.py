"""Photo -> flattened page -> sheet id -> bubble states. Pure image work, no database."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.scanner import align, omr, qr


@dataclass
class PageRead:
    ok: bool
    reject_reason: str | None = None
    sheet_id: str | None = None
    page: np.ndarray | None = None
    answers: list[dict] = field(default_factory=list)


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


def locate(img: np.ndarray) -> tuple[np.ndarray | None, str | None, str | None]:
    """Returns (flat page, sheet_id, reject_reason)."""
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
        sid, _ = qr.read_anywhere(img)
        return None, sid, align.quality_reason(gray)
    page = align.warp_page(img, quad)
    sid = qr.read_qr_box(page)
    if sid is None:  # photographed upside down? the QR would be bottom-left
        flipped = cv2.rotate(page, cv2.ROTATE_180)
        sid = qr.read_qr_box(flipped)
        if sid:
            page = flipped
    if sid is None:  # QR found somewhere else on the page: use its position to fix orientation
        sid, centre = qr.read_anywhere(page)
        if sid and centre and centre[1] > 0.5:
            page = cv2.rotate(page, cv2.ROTATE_180)
    if sid is None:
        sid, _ = qr.read_anywhere(img)
    return page, sid, None


def read_answers(page: np.ndarray, n_questions: int) -> list[dict]:
    out = []
    for fills in omr.bubble_fills(page, n_questions):
        res = omr.classify(fills)
        res["fill"] = fills
        out.append(res)
    return out
