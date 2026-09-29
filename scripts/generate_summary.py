#!/usr/bin/env python3
"""
Build the short visual country summary (title page + ~4 pages) from:
  - the verified profile JSON (source of every fact and citation), and
  - a summary JSON written from it (see .claude/skills/country-profile/SKILL.md).

Usage: python3 generate_summary.py <profile.json> <summary.json> <output.docx>

Citations in the summary use {{group.section:n}}, meaning source n of that profile
section. They are printed with the SAME numbers as the profile's _SOURCES document,
so one sources document serves both.

Charts are defined in CHARTS below per country: every data point names the profile
text it comes from, and the build fails if that number is not in that text.
"""
import json
import re
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_profile as gp  # noqa: E402

# Validated with the dataviz validator (light mode): all checks pass.
INDIA_RED = "#D91F2C"
COMPARE_BLUE = "#2a78d6"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
REF = re.compile(r"\{\{(\w+)\.(\w+):(\d+)\}\}")


# ---------------------------------------------------------------- profile access

def section(profile, group, key):
    r = profile["research"]
    return r["recent_developments"][int(key)] if group == "recent_developments" else r[group][key]


def section_texts(sec):
    out = [sec.get("narrative", ""), sec.get("closing", ""), sec.get("summary", "")]
    out += [f["value"] for f in sec.get("facts", [])]
    out += [e.get("text", "") for e in sec.get("entries", [])]
    return [t for t in out if t]


def cite_numbers(profile, registry, refs):
    nums = []
    for group, key, n in refs:
        src = section(profile, group, key)["sources"][int(n) - 1]
        g = registry.number(src)
        if g not in nums:
            nums.append(g)
    return nums


def markers_near(profile, group, key, needle):
    """Citation refs attached to the profile sentence/fact containing needle."""
    for t in section_texts(section(profile, group, key)):
        i = t.find(needle)
        if i < 0:
            continue
        tail = t[i:]
        m = re.search(r"((?:\{\{\d+\}\})+)", tail)
        if m:
            return [(group, key, n) for n in re.findall(r"\d+", m.group(1))]
    raise SystemExit(f"Chart value '{needle}' not found in {group}.{key}: fix the chart spec")


# ---------------------------------------------------------------- charts

def style_axes(ax):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def chart_workforce(path):
    cats = ["Doctors", "Nurses", "Hospital beds"]
    india = [0.95, 2.60, 0.6]
    oecd = [4.0, 9.2, 4.0]
    fig, ax = plt.subplots(figsize=(6.4, 2.7), dpi=220)
    y = range(len(cats))
    h = 0.36
    ax.barh([i - h / 2 - 0.02 for i in y], india, height=h, color=INDIA_RED, label="India")
    ax.barh([i + h / 2 + 0.02 for i in y], oecd, height=h, color=COMPARE_BLUE, label="OECD average")
    labels_india = ["0.95", "2.60", "<0.6 (public)"]
    for i, (a, b) in enumerate(zip(india, oecd)):
        ax.text(a + 0.12, i - h / 2 - 0.02, labels_india[i], va="center", fontsize=8.5, color=INK)
        ax.text(b + 0.12, i + h / 2 + 0.02, f"{b:g}", va="center", fontsize=8.5, color=INK)
    ax.set_yticks(list(y), cats, fontsize=9.5, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 10.5)
    ax.set_xlabel("per 1,000 people", fontsize=8.5, color=INK_2)
    style_axes(ax)
    ax.legend(frameon=False, fontsize=8.5, loc="lower right", labelcolor=INK)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def chart_spending(path):
    fig, ax = plt.subplots(figsize=(6.4, 2.8), dpi=220)
    x = [0, 1]
    series = [("Out-of-pocket (households)", [64.2, 43.4], INDIA_RED, -9),
              ("Government", [28.6, 43.7], COMPARE_BLUE, 9)]
    for name, ys, color, end_dy in series:
        ax.plot(x, ys, color=color, linewidth=2, marker="o", markersize=7, label=name)
        ax.annotate(f"{ys[0]:g}%", (0, ys[0]), textcoords="offset points", xytext=(-10, 0), ha="right", va="center", fontsize=9, color=INK)
        ax.annotate(f"{ys[1]:g}%", (1, ys[1]), textcoords="offset points", xytext=(10, end_dy), ha="left", va="center", fontsize=9, color=INK)
    ax.set_xticks(x, ["2013-14", "2022-23"], fontsize=9.5, color=INK)
    ax.set_xlim(-0.35, 1.35)
    ax.set_ylim(20, 75)
    ax.set_ylabel("share of total health spending (%)", fontsize=8.5, color=INK_2)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(AXIS)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8.5, loc="upper center", ncol=2, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def chart_chains(path):
    names = ["Manipal Hospitals", "Apollo Hospitals*", "Aster DM Quality Care", "Max Healthcare", "Medicover India"]
    beds = [13037, 10970, 10600, 4966, 4800]
    labels = ["13,037", "10,970", "10,600+", "4,966", "about 4,800"]
    fig, ax = plt.subplots(figsize=(6.4, 2.6), dpi=220)
    ax.barh(range(len(names)), beds, height=0.55, color=INDIA_RED)
    for i, (b, lab) in enumerate(zip(beds, labels)):
        ax.text(b + 180, i, lab, va="center", fontsize=8.5, color=INK)
    ax.set_yticks(range(len(names)), names, fontsize=9.5, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 15500)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_xlabel("beds", fontsize=8.5, color=INK_2)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


CHARTS = {
    "India": {
        "workforce": {
            "draw": chart_workforce,
            "title": "Health workforce and beds per 1,000 people: India vs OECD average",
            "note": "India: registered allopathic doctors (fewer are active) and registered nursing personnel, 2025; "
                    "beds counts public facilities only, March 2023. OECD: averages from Health at a Glance 2025.",
            "values": [("health_system", "workforce", "Roughly 0.95"), ("health_system", "workforce", "2.60 per 1,000 people"),
                       ("health_system", "workforce", "fewer than 0.6 per 1,000"), ("health_system", "workforce", "9.2 nurses")],
        },
        "spending": {
            "draw": chart_spending,
            "title": "Who pays for health care: share of total health spending",
            "note": "National Health Accounts. In between, the out-of-pocket share dipped to 39.4% in COVID-affected 2021-22 "
                    "before rising again once emergency government spending ended.",
            "values": [("health_system", "financing", "43.7% (2022-23), up from 28.6%"),
                       ("health_system", "financing", "43.4% (2022-23), up from 39.4% in 2021-22 and down from 64.2%")],
        },
        "chains": {
            "draw": chart_chains,
            "title": "Largest private hospital groups by beds, 2026",
            "note": "Definitions differ: Manipal licensed beds and Max operational beds (31 March 2026); *Apollo includes "
                    "managed and overseas hospitals and day-surgery units (March 2026); Aster DM Quality Care after its "
                    "July 2026 merger; Medicover India is being acquired by KKR.",
            "values": [("health_system", "private_system", "13,037"), ("health_system", "private_system", "10,970"),
                       ("health_system", "private_system", "10,600"), ("health_system", "private_system", "4,966"),
                       ("health_system", "competitive_landscape", "4,800")],
        },
    }
}


# ---------------------------------------------------------------- docx

def cited_paragraph(doc, text, profile, registry, style=None, size=10.5, color=None):
    p = doc.add_paragraph(style=style) if style else doc.add_paragraph()
    pos = 0
    for m in REF.finditer(text):
        chunk = text[pos:m.start()]
        pos = m.end()
        if chunk:
            r = p.add_run(chunk)
            r.font.size = Pt(size)
            if color:
                r.font.color.rgb = color
        # gather a run of adjacent refs into one citation group
        gp.add_citations(p, cite_numbers(profile, registry, [m.groups()]), registry)
    tail = text[pos:]
    if tail:
        r = p.add_run(tail)
        r.font.size = Pt(size)
        if color:
            r.font.color.rgb = color
    return p


def heading(doc, text):
    h = doc.add_heading(text, level=1)
    h.paragraph_format.space_before = Pt(0)
    h.paragraph_format.space_after = Pt(4)
    gp.add_rule(doc)
    return h


def subhead(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(12)
    r.font.color.rgb = gp.DARK_RED
    return p


def bullets(doc, items, profile, registry):
    for it in items:
        p = cited_paragraph(doc, it, profile, registry, style="List Bullet", size=10.5)
        p.paragraph_format.space_after = Pt(3)


def add_chart(doc, spec, png, profile, registry, width):
    t = doc.add_paragraph()
    t.paragraph_format.space_before = Pt(8)
    t.paragraph_format.space_after = Pt(2)
    tr = t.add_run(spec["title"])
    tr.bold = True
    tr.font.size = Pt(10.5)
    doc.add_picture(str(png), width=width)
    refs = []
    for group, key, needle in spec["values"]:
        refs += markers_near(profile, group, key, needle)
    note = doc.add_paragraph()
    note.paragraph_format.space_after = Pt(8)
    nr = note.add_run(spec["note"] + " Sources: ")
    nr.font.size = Pt(8)
    nr.font.color.rgb = gp.GRAY
    gp.add_citations(note, cite_numbers(profile, registry, refs), registry)


def stat_tiles(doc, tiles, profile, registry, cols=4):
    rows = (len(tiles) + cols - 1) // cols
    table = doc.add_table(rows=rows, cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, tile in enumerate(tiles):
        cell = table.cell(i // cols, i % cols)
        gp.set_cell_shading(cell, "F7F5F2")
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(0)
        v = p.add_run(tile["value"])
        v.bold = True
        v.font.size = Pt(18)
        v.font.color.rgb = RGBColor(0x0B, 0x0B, 0x0B)
        lp = cell.add_paragraph()
        lp.paragraph_format.space_after = Pt(6)
        lr = lp.add_run(tile["label"])
        lr.font.size = Pt(8.5)
        lr.font.color.rgb = RGBColor(0x52, 0x51, 0x4E)
        refs = REF.findall(tile.get("cite", ""))
        if refs:
            gp.add_citations(lp, cite_numbers(profile, registry, refs), registry)
    top = gp.OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = gp.OxmlElement(f"w:{edge}")
        el.set(gp.qn("w:val"), "single")
        el.set(gp.qn("w:sz"), "18" if edge in ("insideV", "insideH") else "0")
        el.set(gp.qn("w:color"), "FFFFFF")
        top.append(el)
    tbl_pr = table._tbl.tblPr
    look = tbl_pr.find(gp.qn("w:tblLook"))
    (look.addprevious(top) if look is not None else tbl_pr.append(top))


def competitor_table(doc, rows):
    table = doc.add_table(rows=1, cols=3)
    gp.set_table_borders(table)
    for i, h in enumerate(("US institution", "Partner in India", "Status")):
        cell = table.rows[0].cells[i]
        gp.set_cell_shading(cell, "D91F2C")
        r = cell.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for row in rows:
        cells = table.add_row().cells
        for i, key in enumerate(("institution", "partner", "status")):
            r = cells[i].paragraphs[0].add_run(row.get(key, ""))
            r.font.size = Pt(9)
            r.bold = key == "institution"
    for row in table.rows:
        for i, w in enumerate((Cm(4.2), Cm(6.0), Cm(7.0))):
            row.cells[i].width = w


def build(profile_path, summary_path, out_path):
    profile = json.loads(Path(profile_path).read_text())
    summary = json.loads(Path(summary_path).read_text())
    country = profile["country"]

    # Rebuild the profile's numbering so summary citations match its _SOURCES document.
    registry = gp.SourceRegistry()
    with tempfile.TemporaryDirectory() as tmp:
        gp.build_profile(profile, str(Path(tmp) / "profile.docx"), registry)

    out = Path(out_path)
    chart_dir = out.with_name(f"{country}_summary_charts")
    chart_dir.mkdir(exist_ok=True)

    doc = Document()
    gp.style_document(doc)
    doc.styles["Heading 1"].font.size = Pt(18)
    gp.add_page_number_footer(doc)
    width = gp.usable_width(doc)

    # Title page
    t = gp.add_cover_title(doc, "Country Summary", country)
    t.paragraph_format.space_before = Pt(60)
    doc.add_picture(gp.cover_image_path(profile, str(Path(out_path).with_name(f"{country}_Profile_DRAFT.docx"))), width=width)
    note = doc.add_paragraph()
    note.paragraph_format.space_before = Pt(18)
    nr = note.add_run(
        f"Executive summary of the {country} country profile ({profile.get('generated_date', '')}). "
        f"Superscript numbers refer to the numbered sources in {country}_Profile_DRAFT_SOURCES.docx."
    )
    nr.italic = True
    nr.font.size = Pt(10)
    nr.font.color.rgb = gp.GRAY
    doc.add_page_break()

    # Page 1: at a glance
    heading(doc, "At a Glance")
    stat_tiles(doc, summary["at_a_glance"], profile, registry)
    if summary.get("country_background"):
        subhead(doc, "Country background")
        cited_paragraph(doc, summary["country_background"], profile, registry, size=10.5)
    subhead(doc, "Key takeaways for CSI")
    bullets(doc, summary["key_takeaways"], profile, registry)
    doc.add_page_break()

    specs = CHARTS[country]
    pngs = {}
    for name, spec in specs.items():
        pngs[name] = chart_dir / f"{name}.png"
        spec["draw"](pngs[name])

    # Page 2: health system
    heading(doc, "Health System")
    bullets(doc, summary["health_system"], profile, registry)
    add_chart(doc, specs["spending"], pngs["spending"], profile, registry, Cm(15.5))
    add_chart(doc, specs["workforce"], pngs["workforce"], profile, registry, Cm(15.5))
    doc.add_page_break()

    # Page 3: market and competition
    heading(doc, "Market and Competition")
    bullets(doc, summary["market"], profile, registry)
    add_chart(doc, specs["chains"], pngs["chains"], profile, registry, Cm(15.5))
    subhead(doc, "US academic medical centers in India")
    competitor_table(doc, summary["competitors"])
    cited_paragraph(doc, summary["competitor_note"], profile, registry, size=10).paragraph_format.space_before = Pt(6)
    doc.add_page_break()

    # Page 4: opportunities, risks, recent
    heading(doc, "Opportunities and Risks for CSI")
    subhead(doc, "Opportunities")
    bullets(doc, summary["opportunities"], profile, registry)
    subhead(doc, "Risks and watch items")
    bullets(doc, summary["risks"], profile, registry)
    subhead(doc, "Recent developments")
    for item in summary["recent"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        dr = p.add_run(item["date"] + "   ")
        dr.bold = True
        dr.font.size = Pt(10)
        dr.font.color.rgb = gp.DARK_RED
        pos = 0
        for m in REF.finditer(item["text"]):
            p.add_run(item["text"][pos:m.start()]).font.size = Pt(10)
            gp.add_citations(p, cite_numbers(profile, registry, [m.groups()]), registry)
            pos = m.end()
        p.add_run(item["text"][pos:]).font.size = Pt(10)

    doc.save(out_path)
    print(f"Wrote {out_path} (charts in {chart_dir})")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("Usage: python3 generate_summary.py <profile.json> <summary.json> <output.docx>")
    build(*sys.argv[1:])
