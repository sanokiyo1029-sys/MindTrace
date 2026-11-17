"""Printable A4 sheets: one page per student, QR = 'MT:<sheet_id>' (no personal data)."""
import io
from datetime import date

import qrcode
from reportlab.lib.colors import black, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from app.layout import base, question_blocks

PAGE_H = A4[1]
GREY = HexColor("#555555")


def _y(mm_from_top: float) -> float:
    """ReportLab measures from the bottom; our layout measures from the top."""
    return PAGE_H - mm_from_top * mm


OPTION_W = 33 * mm


def _fit_option(text: str) -> tuple[float, float, int]:
    """Font size, line gap (mm) and max lines so an option fits beside its bubble."""
    for size, gap, lines in ((11, 4.5, 2), (9.5, 3.9, 2), (8.5, 3.3, 3)):
        if len(simpleSplit(text, "Helvetica", size, OPTION_W)) <= lines:
            return size, gap, lines
    return 8.5, 3.3, 3


def _qr_image(payload: str):
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    q.add_data(payload)
    q.make(fit=True)
    img = q.make_image(fill_color="black", back_color="white").convert("RGB")
    return ImageReader(img)


def _draw_sheet(c: canvas.Canvas, *, sheet: dict, assessment: dict, questions: list[dict]):
    L = base()
    s = L["marker_size_mm"]
    # corner markers (solid squares; the scanner finds these to straighten the photo)
    c.setFillColor(black)
    for cx, cy in L["marker_centres_mm"].values():
        c.rect((cx - s / 2) * mm, _y(cy + s / 2), s * mm, s * mm, stroke=0, fill=1)

    # QR
    qr = L["qr"]
    c.drawImage(_qr_image(f"MT:{sheet['sheet_id']}"), qr["x"] * mm, _y(qr["y"] + qr["size"]),
                qr["size"] * mm, qr["size"] * mm)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString((qr["x"] + qr["size"] / 2) * mm, _y(qr["y"] + qr["size"] + 4.2), sheet["short_code"])

    # header
    hx, hy = L["header"]["x"], L["header"]["y"]
    c.setFont("Helvetica-Bold", 15)
    c.drawString(hx * mm, _y(hy + 3), f"MINDTRACE / {assessment['topic'].upper()}")
    c.setFont("Helvetica", 11)
    c.drawString(hx * mm, _y(hy + 11), f"Student: {sheet['student_name']}    Class: {sheet['class_name']}")
    c.drawString(hx * mm, _y(hy + 18), f"Sheet: {sheet['short_code']}    Date: {date.today():%d %b %Y}")
    c.setFillColor(GREY)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(hx * mm, _y(hy + 26), "Fill ONE bubble per question completely with a dark pen. Then explain why.")
    c.setFillColor(black)
    c.setLineWidth(0.6)
    c.line(20 * mm, _y(L["rule_y_mm"]), 155 * mm, _y(L["rule_y_mm"]))

    r = L["bubble_radius_mm"]
    for qd, block in zip(questions, question_blocks(len(questions))):
        sx, sy = block["stem_xy"]
        c.setFont("Helvetica-Bold", 12)
        lines = simpleSplit(f"Q{block['index'] + 1}. {qd['stem']}", "Helvetica-Bold", 12, 170 * mm)
        for k, line in enumerate(lines[:2]):
            c.drawString(sx * mm, _y(sy + 1 + k * 5.2), line)
        for opt, (bx, by) in block["bubbles"].items():
            c.setFont("Helvetica-Bold", 11)
            c.drawCentredString((bx + L["letter_offset_mm"]) * mm, _y(by + 1.5), opt)
            c.setLineWidth(0.8)
            c.circle(bx * mm, _y(by), r * mm, stroke=1, fill=0)
            size, gap, max_lines = _fit_option(str(qd["options"][opt]))
            c.setFont("Helvetica", size)
            text = simpleSplit(str(qd["options"][opt]), "Helvetica", size, OPTION_W)
            for k, line in enumerate(text[:max_lines]):
                c.drawString((bx + L["option_text_offset_mm"]) * mm, _y(by + 1.5 + k * gap), line)
        x0, y0, x1, y1 = block["why_box"]
        c.setLineWidth(0.5)
        c.setStrokeColor(GREY)
        c.rect(x0 * mm, _y(y1), (x1 - x0) * mm, (y1 - y0) * mm, stroke=1, fill=0)
        c.setStrokeColor(black)
        c.setFillColor(GREY)
        c.setFont("Helvetica-Oblique", 9)
        c.drawString((x0 + 2) * mm, _y(y0 + 4), "Why did you choose this answer?")
        c.setFillColor(black)


def build_pdf(*, assessment: dict, questions: list[dict], sheets: list[dict]) -> bytes:
    """sheets: [{sheet_id, short_code, student_name, class_name}]"""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"MindTrace - {assessment['title']}")
    for sheet in sheets:
        _draw_sheet(c, sheet=sheet, assessment=assessment, questions=questions)
        c.showPage()
    c.save()
    return buf.getvalue()
