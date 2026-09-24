#!/usr/bin/env python3
"""
Generate a Cedars-Sinai International country profile .docx from a structured
JSON file (see schema/profile.example.json).

Usage:
    python3 generate_profile.py <input.json> <output.docx>

The JSON has two kinds of content, and the generator visually distinguishes them
on purpose:

  1. "research" sections: facts an agent gathered from public sources. Every
     fact carries a citation. These render as normal body text with a small
     source line under each subsection.

  2. "csi_manual" section: fields that must come from Cedars-Sinai's own
     internal data (patient volume, revenue, referral relationships, contact
     names, sensitive judgment calls). These render with a highlighted
     "[MANUAL INPUT REQUIRED]" placeholder if left blank, so nobody mistakes
     an unfilled field for a researched fact, and nobody mistakes agent output
     for internal data.
"""
import json
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.text import WD_COLOR_INDEX

CEDARS_RED = RGBColor(0xD9, 0x1F, 0x2C)
GRAY = RGBColor(0x66, 0x66, 0x66)
PLACEHOLDER_COLOR = RGBColor(0xB8, 0x86, 0x00)

MANUAL_PLACEHOLDER = "[MANUAL INPUT REQUIRED]"


def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = CEDARS_RED
    return h


def add_source_line(doc, sources):
    if not sources:
        return
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run("Sources: " + "; ".join(sources))
    run.italic = True
    run.font.size = Pt(8.5)
    run.font.color.rgb = GRAY


def add_fact_block(doc, facts):
    """facts: list of {label, value, source} rendered as a bullet list."""
    for fact in facts:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(f"{fact['label']}: ")
        run.bold = True
        p.add_run(str(fact["value"]))


def add_manual_field(doc, label, value):
    p = doc.add_paragraph()
    run = p.add_run(f"{label}: ")
    run.bold = True
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

    # Title page
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = title.add_run("Country Profile & Market Intelligence:")
    run.font.size = Pt(22)
    run.font.color.rgb = CEDARS_RED
    run.bold = True
    title2 = doc.add_paragraph()
    run2 = title2.add_run(data["country"])
    run2.font.size = Pt(30)
    run2.font.color.rgb = CEDARS_RED
    run2.bold = True

    meta = doc.add_paragraph()
    meta_run = meta.add_run(
        f"Draft generated {data.get('generated_date', '')} — "
        f"public-source sections are agent-researched and verified; "
        f"the CSI Assessment section requires manual completion from internal data."
    )
    meta_run.italic = True
    meta_run.font.color.rgb = GRAY

    doc.add_page_break()

    # ---- Country Overview ----
    add_heading(doc, "Country Overview", level=1)
    overview = data["research"]["country_overview"]
    add_heading(doc, "Population and Demographics", level=2)
    add_fact_block(doc, overview["demographics"]["facts"])
    add_source_line(doc, overview["demographics"].get("sources", []))

    add_heading(doc, "Government", level=2)
    doc.add_paragraph(overview["government"]["narrative"])
    add_source_line(doc, overview["government"].get("sources", []))

    add_heading(doc, "Economy", level=2)
    doc.add_paragraph(overview["economy"]["narrative"])
    add_source_line(doc, overview["economy"].get("sources", []))

    add_heading(doc, "Disease Prevalence", level=2)
    add_fact_block(doc, overview["disease_prevalence"]["facts"])
    add_source_line(doc, overview["disease_prevalence"].get("sources", []))

    # ---- Health System ----
    add_heading(doc, f"{data['country']} Health System", level=1)
    hs = data["research"]["health_system"]
    for section_key, title in [
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
        add_heading(doc, title, level=2)
        if "facts" in section:
            add_fact_block(doc, section["facts"])
        if "narrative" in section:
            doc.add_paragraph(section["narrative"])
        add_source_line(doc, section.get("sources", []))

    # ---- Recent Developments ----
    rd = data["research"].get("recent_developments", [])
    if rd:
        add_heading(doc, "Recent Developments", level=1)
        for item in rd:
            p = doc.add_paragraph()
            date_run = p.add_run(f"{item['date']} — ")
            date_run.bold = True
            title_run = p.add_run(item["headline"])
            title_run.italic = True
            doc.add_paragraph(item["summary"])
            add_source_line(doc, item.get("sources", []))

    # ---- Verification note ----
    doc.add_page_break()
    add_heading(doc, "Fact-Verification Notes", level=1)
    v = data.get("verification_report", {})
    doc.add_paragraph(
        "This section is generated by a second, independent review pass whose "
        "only job is to check every factual claim above against its cited source "
        "and flag anything unsupported, stale, or contradicted. It is retained "
        "in the draft for reviewer transparency and should be resolved (and then "
        "deleted) before the profile is finalized."
    )
    flagged = v.get("flagged_claims", [])
    if flagged:
        for item in flagged:
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(f"[{item.get('severity', 'flag').upper()}] ")
            run.bold = True
            run.font.color.rgb = PLACEHOLDER_COLOR
            p.add_run(f"{item['claim']} — {item['issue']}")
    else:
        doc.add_paragraph("No unresolved flags from the verification pass.")

    # ---- CSI Assessment (manual) ----
    doc.add_page_break()
    add_heading(doc, "CSI Assessment", level=1)
    note = doc.add_paragraph()
    note_run = note.add_run(
        "Everything below comes from Cedars-Sinai's internal data (patient "
        "referral records, finance, relationship history) and human judgment, "
        "not from the research agent. Fields left blank are marked and must be "
        "completed by the analyst before this profile is used."
    )
    note_run.italic = True
    note_run.font.color.rgb = GRAY

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
        doc.add_paragraph()

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
