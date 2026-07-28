#!/usr/bin/env python3
"""Minimal, robust Markdown -> PDF renderer (reportlab) for the SILO model report.

Supports: #/##/###/#### headings, body paragraphs, - and 1. lists, ```fenced code```
blocks (monospaced, shaded, line-wrapped), > callouts, --- rules, **bold**, `inline code`,
and simple pipe tables. Designed for long technical docs with many code snippets.

Usage: python md2pdf.py input.md output.pdf "Document Title"
"""
import sys, re, html
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Preformatted, Table, TableStyle, HRFlowable, KeepTogether)
from reportlab.lib.enums import TA_LEFT

MD = sys.argv[1]; OUT = sys.argv[2]; TITLE = sys.argv[3] if len(sys.argv) > 3 else "Document"

styles = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica",
                      fontSize=9.5, leading=13.5, spaceBefore=2, spaceAfter=5, alignment=TA_LEFT)
H1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                    fontSize=17, leading=21, spaceBefore=16, spaceAfter=7, textColor=colors.HexColor("#1F3B63"))
H2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                    fontSize=13, leading=17, spaceBefore=12, spaceAfter=5, textColor=colors.HexColor("#234E70"))
H3 = ParagraphStyle("h3", parent=styles["Heading3"], fontName="Helvetica-Bold",
                    fontSize=11, leading=14, spaceBefore=9, spaceAfter=3, textColor=colors.HexColor("#2F5C82"))
H4 = ParagraphStyle("h4", parent=styles["Heading4"], fontName="Helvetica-BoldOblique",
                    fontSize=9.8, leading=13, spaceBefore=7, spaceAfter=2, textColor=colors.HexColor("#444444"))
CODE = ParagraphStyle("code", fontName="Courier", fontSize=7.4, leading=9.1,
                      textColor=colors.HexColor("#1A1A1A"), backColor=colors.HexColor("#F4F5F7"),
                      borderColor=colors.HexColor("#D0D4DA"), borderWidth=0.5, borderPadding=5,
                      leftIndent=2, spaceBefore=4, spaceAfter=7)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=16, bulletIndent=5, spaceAfter=2)
CALLOUT = ParagraphStyle("callout", parent=BODY, leftIndent=10, backColor=colors.HexColor("#FFF8E1"),
                         borderColor=colors.HexColor("#E0C060"), borderWidth=0.5, borderPadding=6,
                         spaceBefore=4, spaceAfter=7)


def inline(t):
    t = html.escape(html.unescape(t))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r'<font name="Courier" size="8.5" backColor="#EEF0F2">\1</font>', t)
    return t


def wrap_code(line, width=118):
    out = []
    while len(line) > width:
        cut = line.rfind(" ", 0, width)
        if cut < width * 0.6:
            cut = width
        out.append(line[:cut]); line = "    " + line[cut:].lstrip()
    out.append(line); return out


def parse(md):
    fl = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            buf = []; i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                for w in wrap_code(html.unescape(lines[i]).replace("\t", "    ")):
                    buf.append(w)   # Preformatted shows raw text (does NOT parse entities)
                i += 1
            i += 1
            fl.append(Preformatted("\n".join(buf), CODE)); continue
        if ln.startswith("#### "): fl.append(Paragraph(inline(ln[5:]), H4))
        elif ln.startswith("### "): fl.append(Paragraph(inline(ln[4:]), H3))
        elif ln.startswith("## "): fl.append(Paragraph(inline(ln[3:]), H2))
        elif ln.startswith("# "): fl.append(Paragraph(inline(ln[2:]), H1))
        elif ln.strip() in ("---", "***"): fl.append(HRFlowable(width="100%", color=colors.HexColor("#C8CDD4"), spaceBefore=5, spaceAfter=5))
        elif ln.strip().startswith("> "): fl.append(Paragraph(inline(ln.strip()[2:]), CALLOUT))
        elif re.match(r"^\s*[-*] ", ln): fl.append(Paragraph(inline(re.sub(r"^\s*[-*] ", "", ln)), BULLET, bulletText="•"))
        elif re.match(r"^\s*\d+\. ", ln): fl.append(Paragraph(inline(re.sub(r"^\s*\d+\. ", "", ln)), BULLET, bulletText="–"))
        elif ln.strip().startswith("|") and "|" in ln[1:]:
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s:\-]+$", "".join(cells)):
                    rows.append([Paragraph(inline(c), ParagraphStyle("tc", parent=BODY, fontSize=8, leading=10)) for c in cells])
                i += 1
            if rows:
                t = Table(rows, repeatRows=1, hAlign="LEFT")
                t.setStyle(TableStyle([
                    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#C8CDD4")),
                    ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E7EBF0")),
                    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                    ("VALIGN", (0,0), (-1,-1), "TOP"), ("TOPPADDING",(0,0),(-1,-1),3),
                    ("BOTTOMPADDING",(0,0),(-1,-1),3), ("LEFTPADDING",(0,0),(-1,-1),4)]))
                fl.append(t); fl.append(Spacer(1, 6)); continue
        elif ln.strip() == "": fl.append(Spacer(1, 3))
        else: fl.append(Paragraph(inline(ln), BODY))
        i += 1
    return fl


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5); canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(0.75*inch, 0.5*inch, "SILO Land-Use Microsimulation — Model & Mechanism Reference (VAE-SILO-MITO-MATSim)")
    canvas.drawRightString(7.75*inch, 0.5*inch, "p. %d" % doc.page)
    canvas.setStrokeColor(colors.HexColor("#C8CDD4")); canvas.line(0.75*inch, 0.62*inch, 7.75*inch, 0.62*inch)
    canvas.restoreState()


doc = BaseDocTemplate(OUT, pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch,
                      topMargin=0.7*inch, bottomMargin=0.7*inch, title=TITLE)
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
doc.addPageTemplates([PageTemplate(id="t", frames=[frame], onPage=header_footer)])
story = parse(open(MD).read())
doc.build(story)
print(f"wrote {OUT}")
