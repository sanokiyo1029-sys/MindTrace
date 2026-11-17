"""Printable A4 question papers. Every copy is identical: the student writes their roll number in the boxes at
the top, and that (not a QR code or a printed name) is how a scan is matched to the class roster."""
import io
from datetime import date

from reportlab.lib.colors import black, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from app.layout import base, paper_code, question_blocks, question_types

PAGE_H = A4[1]
GREY = HexColor("#555555")


def _y(mm_from_top: float) -> float:
    """ReportLab measures from the bottom; our layout measures from the top."""
    return PAGE_H - mm_from_top * mm


OPTION_W = 28 * mm  # leaves a gap before the next option's letter


def _fit_option(text: str) -> tuple[float, float, int]:
    """Font size, line gap (mm) and max lines so an option fits beside its bubble."""
    for size, gap, lines in ((11, 4.5, 2), (9.5, 3.9, 2), (8.5, 3.3, 3)):
        if len(simpleSplit(text, "Helvetica", size, OPTION_W)) <= lines:
            return size, gap, lines
    return 8.5, 3.3, 3


def _labelled_box(c: canvas.Canvas, label: str, x: float, y: float, w: float, h: float, cells: int = 1):
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x * mm, _y(y - 1.8), label)
    c.setLineWidth(1.3)
    for i in range(cells):
        cw = w / cells
        c.rect((x + i * cw) * mm, _y(y + h), cw * mm, h * mm, stroke=1, fill=0)


def _draw_sheet(c: canvas.Canvas, *, assessment: dict, questions: list[dict], page: int = 1, pages: int = 1):
    L = base()
    s = L["marker_size_mm"]
    # corner markers (solid squares; the bubble reader uses them to straighten the photo)
    c.setFillColor(black)
    for cx, cy in L["marker_centres_mm"].values():
        c.rect((cx - s / 2) * mm, _y(cy + s / 2), s * mm, s * mm, stroke=0, fill=1)

    # 1. the very top: roll number (one character per box), class/section, page and paper code
    rb = L["roll_box"]
    _labelled_box(c, "ROLL NO.", rb["x"], rb["y"], rb["w"] * rb["count"], rb["h"], cells=rb["count"])
    c.setFillColor(GREY)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString((rb["x"] + 21) * mm, _y(rb["y"] - 1.8), "one character per box, e.g. 0 7")
    c.setFillColor(black)
    cb = L["class_box"]
    _labelled_box(c, "CLASS / SECTION", cb["x"], cb["y"], cb["w"], cb["h"])
    pi = L["page_info"]
    c.setFont("Helvetica-Bold", 12)
    c.drawString(pi["x"] * mm, _y(pi["y"] + 2), f"Page {page} of {pages}")
    c.setFillColor(GREY)
    c.setFont("Helvetica", 8.5)
    c.drawString(pi["x"] * mm, _y(pi["y"] + 8), "Paper code")
    c.setFillColor(black)
    c.setFont("Courier-Bold", 13)
    c.drawString(pi["x"] * mm, _y(pi["y"] + 13.5), assessment["paper_code"])

    # 2. assessment title + instructions
    ty = L["title_y_mm"]
    c.setFont("Helvetica-Bold", 14)
    title = f"{assessment['title']}  ·  Class {assessment['class_name']}"
    c.drawString(25 * mm, _y(ty), simpleSplit(title, "Helvetica-Bold", 14, 165 * mm)[0])
    c.setFillColor(GREY)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(25 * mm, _y(ty + 5.5),
                 f"MindTrace · {date.today():%d %b %Y} · " + (
                     "Roll number above. ONE dark bubble per question, explain why; long answers in their box."
                     if "descriptive" in question_types(questions) else
                     "Write your roll number above. Fill ONE bubble per question with a dark pen, then explain why."))
    c.setFillColor(black)
    c.setLineWidth(0.6)
    c.line(20 * mm, _y(L["rule_y_mm"]), 190 * mm, _y(L["rule_y_mm"]))

    r = L["bubble_radius_mm"]
    for qd, block in zip(questions, question_blocks(len(questions), question_types(questions))):
        sx, sy = block["stem_xy"]
        c.setFont("Helvetica-Bold", 12)
        lines = simpleSplit(f"Q{block['index'] + 1}. {qd['stem']}", "Helvetica-Bold", 12, 170 * mm)
        for k, line in enumerate(lines[:2]):
            c.drawString(sx * mm, _y(sy + 1 + k * 5.2), line)
        if block["type"] == "descriptive":
            _answer_box(c, block["why_box"])
            continue
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
        c.drawString((x0 + 2) * mm, _y(y0 + 4), "Why did you choose this answer? (working and notes)")
        c.setFillColor(black)


def _answer_box(c: canvas.Canvas, box):
    """Written-answer box with faint ruled lines (kept light so they don't look like ink to the reader)."""
    x0, y0, x1, y1 = box
    c.setLineWidth(0.8)
    c.setStrokeColor(GREY)
    c.rect(x0 * mm, _y(y1), (x1 - x0) * mm, (y1 - y0) * mm, stroke=1, fill=0)
    c.setStrokeColor(HexColor("#C8C8C8"))
    c.setLineWidth(0.3)
    y = y0 + 15
    while y < y1 - 3:
        c.line((x0 + 3) * mm, _y(y), (x1 - 3) * mm, _y(y))
        y += 8
    c.setStrokeColor(black)
    c.setFillColor(GREY)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString((x0 + 2) * mm, _y(y0 + 4), "Write your answer here. Show your working and any notes.")
    c.setFillColor(black)


def build_pdf(*, assessment: dict, questions: list[dict], copies: int) -> bytes:
    """assessment: {id, title, topic, class_name}. One identical single-page paper per copy."""
    assessment = {**assessment, "paper_code": paper_code(assessment["id"])}
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"MindTrace - {assessment['title']}")
    for _ in range(max(1, copies)):
        _draw_sheet(c, assessment=assessment, questions=questions)
        c.showPage()
    c.save()
    return buf.getvalue()
