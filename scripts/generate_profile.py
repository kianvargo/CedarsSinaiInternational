#!/usr/bin/env python3
"""
Generate a Cedars-Sinai International country profile .docx from a structured
JSON file (see schema/profile.example.json).

Usage:
    python3 generate_profile.py <input.json> <output.docx>

Two kinds of content, rendered differently on purpose:

  1. "research" sections: facts an agent gathered from public sources,
     independently fact-checked, with corrections already merged into the
     text itself (no separate "flagged claims" appendix in the document).
     A small source line follows each subsection for traceability.

  2. "csi_manual" section: fields that must come from Cedars-Sinai's own
     internal data. These render with a highlighted "[MANUAL INPUT
     REQUIRED]" placeholder if left blank.
"""
import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

CEDARS_RED = RGBColor(0xD9, 0x1F, 0x2C)
DARK_RED = RGBColor(0xB3, 0x18, 0x22)
INK = RGBColor(0x24, 0x24, 0x24)
GRAY = RGBColor(0x6E, 0x6E, 0x6E)
PLACEHOLDER_COLOR = RGBColor(0x99, 0x6A, 0x00)

BODY_FONT = "Calibri"
MANUAL_PLACEHOLDER = "[MANUAL INPUT REQUIRED]"


def set_cell_shading(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def style_document(doc):
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.18

    h1 = doc.styles["Heading 1"]
    h1.font.name = BODY_FONT
    h1.font.size = Pt(20)
    h1.font.bold = True
    h1.font.color.rgb = CEDARS_RED
    h1.paragraph_format.space_before = Pt(22)
    h1.paragraph_format.space_after = Pt(10)

    h2 = doc.styles["Heading 2"]
    h2.font.name = BODY_FONT
    h2.font.size = Pt(14)
    h2.font.bold = True
    h2.font.color.rgb = DARK_RED
    h2.paragraph_format.space_before = Pt(14)
    h2.paragraph_format.space_after = Pt(6)

    bullet = doc.styles["List Bullet"]
    bullet.font.name = BODY_FONT
    bullet.font.size = Pt(11)
    bullet.paragraph_format.space_after = Pt(4)
    bullet.paragraph_format.line_spacing = 1.15

    section = doc.sections[0]
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)


def add_heading(doc, text, level=1):
    return doc.add_heading(text, level=level)


def add_rule(doc, color=CEDARS_RED):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    p_pr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "D91F2C")
    borders.append(bottom)
    p_pr.append(borders)


def add_source_line(doc, sources):
    if not sources:
        return
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run("Sources: " + "; ".join(sources))
    run.italic = True
    run.font.size = Pt(8.5)
    run.font.color.rgb = GRAY


def add_narrative(doc, text):
    if not text:
        return
    for para in re.split(r"\n\s*\n|\n", text):
        if para.strip():
            doc.add_paragraph(para.strip())


def add_facts_table(doc, facts, columns=2):
    """Facts render as a light two-column table (label | value) instead of a
    bullet list, closer to the original template's info-box layout and
    tighter on the page than one bullet per fact."""
    if not facts:
        return
    rows = (len(facts) + columns - 1) // columns
    table = doc.add_table(rows=rows, cols=columns * 2)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = True

    for idx, fact in enumerate(facts):
        row, col_group = divmod(idx, columns)
        label_cell = table.cell(row, col_group * 2)
        value_cell = table.cell(row, col_group * 2 + 1)

        lp = label_cell.paragraphs[0]
        lp.paragraph_format.space_after = Pt(3)
        lrun = lp.add_run(fact["label"])
        lrun.bold = True
        lrun.font.size = Pt(10.5)
        lrun.font.color.rgb = DARK_RED

        vp = value_cell.paragraphs[0]
        vp.paragraph_format.space_after = Pt(3)
        vrun = vp.add_run(str(fact["value"]))
        vrun.font.size = Pt(10.5)

    # fill any unused trailing cells so the table doesn't look ragged
    total_cells = rows * columns
    for idx in range(len(facts), total_cells):
        row, col_group = divmod(idx, columns)
        table.cell(row, col_group * 2).text = ""
        table.cell(row, col_group * 2 + 1).text = ""

    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_manual_field(doc, label, value):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run(f"{label}\n")
    run.bold = True
    run.font.color.rgb = DARK_RED
    text = value.strip() if value else ""
    if not text:
        run2 = p.add_run(MANUAL_PLACEHOLDER)
        run2.bold = True
        run2.font.color.rgb = PLACEHOLDER_COLOR
        run2.font.highlight_color = WD_COLOR_INDEX.YELLOW
    else:
        p.add_run(text)


def build_docx(data: dict, out_path: str):
    doc = Document()
    style_document(doc)

    # ---- Title page ----
    doc.add_paragraph().paragraph_format.space_after = Pt(60)
    kicker = doc.add_paragraph()
    kicker_run = kicker.add_run("COUNTRY PROFILE & MARKET INTELLIGENCE")
    kicker_run.font.size = Pt(13)
    kicker_run.font.color.rgb = GRAY
    kicker_run.bold = True
    kicker.paragraph_format.space_after = Pt(2)

    title = doc.add_paragraph()
    trun = title.add_run(data["country"])
    trun.font.size = Pt(36)
    trun.font.color.rgb = CEDARS_RED
    trun.bold = True
    title.paragraph_format.space_after = Pt(30)

    meta = doc.add_paragraph()
    meta_run = meta.add_run(
        f"Draft prepared {data.get('generated_date', '')}. Public-source "
        f"sections were researched and independently fact-checked before "
        f"this draft was written; the CSI Assessment section requires "
        f"completion from Cedars-Sinai's internal data."
    )
    meta_run.italic = True
    meta_run.font.color.rgb = GRAY
    meta_run.font.size = Pt(10)

    doc.add_page_break()

    # ---- Country Overview ----
    add_heading(doc, "Country Overview", level=1)
    add_rule(doc)
    overview = data["research"]["country_overview"]

    for section_key, title_text in [
        ("demographics", "Population and Demographics"),
        ("government", "Government"),
        ("economy", "Economy"),
        ("disease_prevalence", "Disease Prevalence"),
    ]:
        section = overview.get(section_key)
        if not section:
            continue
        add_heading(doc, title_text, level=2)
        if section.get("facts"):
            add_facts_table(doc, section["facts"])
        if section.get("narrative"):
            add_narrative(doc, section["narrative"])
        add_source_line(doc, section.get("sources", []))

    # ---- Health System ----
    add_heading(doc, f"{data['country']} Health System", level=1)
    add_rule(doc)
    hs = data["research"]["health_system"]
    for section_key, title_text in [
        ("public_system", "Public Healthcare System"),
        ("private_system", "Private Healthcare System"),
        ("financing", "Healthcare Financing"),
        ("workforce", "Workforce"),
        ("education", "Education"),
        ("outlook", "Healthcare Outlook"),
        ("competitive_landscape", "Competitive Landscape"),
    ]:
        section = hs.get(section_key)
        if not section:
            continue
        add_heading(doc, title_text, level=2)
        if section.get("facts"):
            add_facts_table(doc, section["facts"])
        if section.get("narrative"):
            add_narrative(doc, section["narrative"])
        add_source_line(doc, section.get("sources", []))

    # ---- Recent Developments ----
    rd = data["research"].get("recent_developments", [])
    if rd:
        add_heading(doc, "Recent Developments", level=1)
        add_rule(doc)
        for item in rd:
            summary_text = item.get("summary") or item.get("development") or ""
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            date_run = p.add_run(f"{item['date']}  ")
            date_run.bold = True
            date_run.font.color.rgb = DARK_RED
            if item.get("headline"):
                title_run = p.add_run(item["headline"])
                title_run.bold = True
                body = doc.add_paragraph(summary_text)
                body.paragraph_format.space_after = Pt(2)
            else:
                p.add_run(summary_text)
            add_source_line(doc, item.get("sources", []))

    # ---- CSI Assessment (manual) ----
    doc.add_page_break()
    add_heading(doc, "CSI Assessment", level=1)
    add_rule(doc)
    note = doc.add_paragraph()
    note_run = note.add_run(
        "Everything below comes from Cedars-Sinai's internal data (patient "
        "referral records, finance, relationship history) and human judgment, "
        "not from the research agent. Fields left blank are marked and must "
        "be completed by the analyst before this profile is used."
    )
    note_run.italic = True
    note_run.font.color.rgb = GRAY
    note_run.font.size = Pt(10)

    manual = data.get("csi_manual", {})
    manual_fields = [
        ("patient_volume_and_revenue", "Patient Volume & Revenue (most recent FY)"),
        ("referral_sources", "Referral Sources"),
        ("relationship_history", "Relationship History"),
        ("complications", "Complications"),
        ("key_contacts", "Key Contacts"),
        ("opportunities", "Opportunities"),
        ("csi_recommendation", "CSI Recommendation"),
    ]
    for key, label in manual_fields:
        add_manual_field(doc, label, manual.get(key, ""))

    doc.save(out_path)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 generate_profile.py <input.json> <output.docx>")
        sys.exit(1)
    input_path, output_path = sys.argv[1], sys.argv[2]
    data = json.loads(Path(input_path).read_text())
    build_docx(data, output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
