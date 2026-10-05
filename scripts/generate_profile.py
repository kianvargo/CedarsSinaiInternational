#!/usr/bin/env python3
"""
Generate a Cedars-Sinai International country profile from structured JSON
(see .claude/skills/country-profile/schema/profile.example.json).

Usage:
    python3 generate_profile.py <input.json> <output.docx>

Writes two files:
  <output.docx>                the profile: cover map, linked table of contents,
                               numbered superscript citations
  <output>_SOURCES.docx        the numbered reference list those citations point to

Citations: narrative text, fact values and recent-development summaries may
contain markers like {{3}}, meaning "source 3 in this section's sources list".
They are renumbered into one document-wide sequence in order of first use.
Sections without markers get their sources cited at the end of the section.
Sources may be plain "Name, URL" strings or objects with author/title/
publisher/date/url.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX, WD_TAB_LEADER
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

CEDARS_RED = RGBColor(0xD9, 0x1F, 0x2C)
DARK_RED = RGBColor(0xB3, 0x18, 0x22)
INK = RGBColor(0x24, 0x24, 0x24)
GRAY = RGBColor(0x6E, 0x6E, 0x6E)
PLACEHOLDER_COLOR = RGBColor(0x99, 0x6A, 0x00)

BODY_FONT = "Calibri"
MANUAL_PLACEHOLDER = "[MANUAL INPUT REQUIRED]"
MARKER = re.compile(r"((?:\{\{\d+\}\})+)")
URL_RE = re.compile(r"https?://\S+")
SCRIPTS = Path(__file__).resolve().parent

OVERVIEW_SECTIONS = [
    ("demographics", "Population and Demographics"),
    ("government", "Government"),
    ("economy", "Economy"),
    ("disease_prevalence", "Disease Prevalence"),
]
HEALTH_SECTIONS = [
    ("public_system", "Public Healthcare System"),
    ("private_system", "Private Healthcare System"),
    ("financing", "Healthcare Financing"),
    ("workforce", "Workforce"),
    ("education", "Education"),
    ("outlook", "Healthcare Outlook"),
    ("competitive_landscape", "Competitive Landscape"),
]


# ---------------------------------------------------------------- sources

class SourceRegistry:
    """Assigns document-wide citation numbers in order of first use."""

    def __init__(self):
        self.entries = []
        self.index = {}

    @staticmethod
    def key(src):
        if isinstance(src, dict):
            return (src.get("url") or src.get("title") or json.dumps(src, sort_keys=True)).rstrip("/").lower()
        m = URL_RE.search(src)
        return (m.group(0) if m else src).rstrip("/").lower()

    def number(self, src):
        k = self.key(src)
        if k not in self.index:
            self.entries.append(src)
            self.index[k] = len(self.entries)
        return self.index[k]


def source_url(src):
    if isinstance(src, dict):
        return src.get("url") or ""
    m = URL_RE.search(src)
    return m.group(0).rstrip(").,;") if m else ""


def format_reference(src):
    """Returns (text_before_url, url)."""
    if isinstance(src, dict):
        parts = []
        if src.get("author"):
            parts.append(src["author"].rstrip(".") + ".")
        if src.get("title"):
            parts.append(f"“{src['title'].rstrip('.')}.”")
        tail = ", ".join(x for x in (src.get("publisher", ""), src.get("date", "")) if x)
        if tail:
            parts.append(tail + ".")
        return " ".join(parts), src.get("url", "")
    url = source_url(src)
    text = src.replace(url, "").strip().rstrip(",").strip()
    return (text + "." if text and not text.endswith(".") else text), url


# ---------------------------------------------------------------- docx helpers

def style_document(doc):
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.18

    for name, size, color, before, after in (("Heading 1", 20, CEDARS_RED, 22, 10), ("Heading 2", 14, DARK_RED, 14, 6)):
        h = doc.styles[name]
        h.font.name = BODY_FONT
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.color.rgb = color
        h.paragraph_format.space_before = Pt(before)
        h.paragraph_format.space_after = Pt(after)

    section = doc.sections[0]
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)


def update_fields_on_open(doc):
    """Ask Word to refresh page-number fields (table of contents) when opened."""
    settings = doc.settings.element
    el = OxmlElement("w:updateFields")
    el.set(qn("w:val"), "true")
    # schema order: updateFields must precede these elements
    for tag in ("hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids",
                "themeFontLang", "clrSchemeMapping", "decimalSymbol", "listSeparator"):
        anchor = settings.find(qn(f"w:{tag}"))
        if anchor is not None:
            anchor.addprevious(el)
            return
    settings.append(el)


def add_page_number_footer(doc):
    p = doc.sections[0].footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run("Cedars-Sinai International   ")
    r.font.size = Pt(9)
    r.font.color.rgb = GRAY
    add_field(p, "PAGE", "", size=9, color=GRAY)


def usable_width(doc):
    s = doc.sections[0]
    return s.page_width - s.left_margin - s.right_margin


COVER_RED = RGBColor(0xCC, 0x00, 0x00)


def add_cover_title(doc, doc_type, country):
    """'Country Profile: India' in 20pt red, document type in bold."""
    p = doc.add_paragraph()
    for text, bold in ((f"{doc_type}: ", True), (country, False)):
        r = p.add_run(text)
        r.bold = bold
        r.font.size = Pt(20)
        r.font.color.rgb = COVER_RED
    return p


def add_field(paragraph, instr, cached, size=None, color=None):
    def run_with(child):
        r = OxmlElement("w:r")
        if size or color:
            rpr = OxmlElement("w:rPr")
            if color:
                c = OxmlElement("w:color")
                c.set(qn("w:val"), str(color))
                rpr.append(c)
            if size:
                sz = OxmlElement("w:sz")
                sz.set(qn("w:val"), str(int(size * 2)))
                rpr.append(sz)
            r.append(rpr)
        r.append(child)
        paragraph._p.append(r)

    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    run_with(begin)
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    run_with(it)
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    run_with(sep)
    t = OxmlElement("w:t")
    t.text = cached
    run_with(t)
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run_with(end)


class Headings:
    def __init__(self):
        self.items = []  # (level, text, bookmark)

    def add(self, doc, text, level):
        h = doc.add_heading(text, level=level)
        name = f"_sec{len(self.items) + 1}"
        start = OxmlElement("w:bookmarkStart")
        start.set(qn("w:id"), str(len(self.items) + 1))
        start.set(qn("w:name"), name)
        end = OxmlElement("w:bookmarkEnd")
        end.set(qn("w:id"), str(len(self.items) + 1))
        h._p.insert(1 if h._p.pPr is not None else 0, start)
        h._p.append(end)
        self.items.append((level, text, name))
        return h


def add_internal_link(paragraph, text, anchor, bold=False, italic=False):
    link = OxmlElement("w:hyperlink")
    link.set(qn("w:anchor"), anchor)
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    if bold:
        rpr.append(OxmlElement("w:b"))
    if italic:
        rpr.append(OxmlElement("w:i"))
    r.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    link.append(r)
    paragraph._p.append(link)


def add_external_link(paragraph, text, url, superscript=False, size=None, color="B31822"):
    r_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color)
    rpr.append(c)
    if size:
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(size * 2)))
        rpr.append(sz)
    if superscript:
        va = OxmlElement("w:vertAlign")
        va.set(qn("w:val"), "superscript")
        rpr.append(va)
    r.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    link.append(r)
    paragraph._p.append(link)


def add_citations(paragraph, numbers, registry):
    for i, n in enumerate(numbers):
        src = registry.entries[n - 1]
        label = str(n) + ("," if i < len(numbers) - 1 else "")
        url = source_url(src)
        if url:
            add_external_link(paragraph, label, url, superscript=True)
        else:
            r = paragraph.add_run(label)
            r.font.superscript = True
            r.font.color.rgb = DARK_RED


def add_cited_text(paragraph, text, sources, registry, size=None):
    """Writes text into paragraph, turning {{n}} markers into superscript citations.
    Returns True if the text contained any marker."""
    found = False
    for chunk in MARKER.split(text):
        if not chunk:
            continue
        if MARKER.fullmatch(chunk):
            local = [int(x) for x in re.findall(r"\d+", chunk)]
            nums = []
            for n in local:
                if 1 <= n <= len(sources):
                    g = registry.number(sources[n - 1])
                    if g not in nums:
                        nums.append(g)
            add_citations(paragraph, sorted(nums), registry)
            found = True
        else:
            r = paragraph.add_run(chunk)
            if size:
                r.font.size = Pt(size)
    return found


def add_rule(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("val", "single"), ("sz", "12"), ("space", "1"), ("color", "D91F2C")):
        bottom.set(qn(f"w:{k}"), v)
    borders.append(bottom)
    p._p.get_or_add_pPr().append(borders)


def add_facts_table(doc, facts, sources, registry, columns=2):
    rows = (len(facts) + columns - 1) // columns
    table = doc.add_table(rows=rows, cols=columns * 2)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = True
    cited = False
    for idx, fact in enumerate(facts):
        row, group = divmod(idx, columns)
        lp = table.cell(row, group * 2).paragraphs[0]
        lp.paragraph_format.space_after = Pt(3)
        lrun = lp.add_run(fact["label"])
        lrun.bold = True
        lrun.font.size = Pt(10.5)
        lrun.font.color.rgb = DARK_RED
        vp = table.cell(row, group * 2 + 1).paragraphs[0]
        vp.paragraph_format.space_after = Pt(3)
        cited |= add_cited_text(vp, str(fact["value"]), sources, registry, size=10.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return cited


def add_section_body(doc, section, registry):
    sources = section.get("sources", [])
    cited = False
    if section.get("facts"):
        cited |= add_facts_table(doc, section["facts"], sources, registry)
    last = None
    for para in re.split(r"\n\s*\n|\n", section.get("narrative", "") or ""):
        if para.strip():
            last = doc.add_paragraph()
            cited |= add_cited_text(last, para.strip(), sources, registry)
    if section.get("tracker_country"):
        add_tracker_block(doc, section["tracker_country"], registry)
        cited = True
    elif section.get("entries"):
        cited |= add_entries(doc, section["entries"], sources, registry)
    for para in re.split(r"\n\s*\n|\n", section.get("closing", "") or ""):
        if para.strip():
            last = doc.add_paragraph()
            cited |= add_cited_text(last, para.strip(), sources, registry)
    if sources and not cited:
        # no per-sentence markers: cite the section's sources at its end
        if last is None:
            last = doc.add_paragraph()
        add_citations(last, sorted({registry.number(s) for s in sources}), registry)


def set_cell_shading(cell, hex_fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    cell._tc.get_or_add_tcPr().append(shd)


def set_table_borders(table, color="D9D9D9"):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    for tag in ("shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription"):
        anchor = tbl_pr.find(qn(f"w:{tag}"))
        if anchor is not None:
            anchor.addprevious(borders)
            return
    tbl_pr.append(borders)


ROOT = SCRIPTS.parent
MAP_CAPTION = ("Active foreign health-system partnerships by city of the partner in {country}. "
               "Source: CSI partnerships tracker, verified {checked}. Boundaries: Natural Earth; not an official depiction.")
GROUPS = ("US academic medical centers", "Other foreign health systems")


def partner_map(country, out_dir):
    """Map of active partnerships, or None when the country has no partner-location file yet."""
    png = Path(out_dir) / f"{country}_partnerships_map.png"
    locs = ROOT / "data" / f"{country.lower().replace(' ', '_')}_partner_locations.json"
    if not locs.exists():
        return None
    subprocess.run([sys.executable, str(SCRIPTS / "make_partner_map.py"), country, str(png)], check=True,
                   capture_output=True)
    return png


def tracker_rows(country, status=None):
    data = json.loads((ROOT / "data" / "partnerships.json").read_text())
    return [r for r in data["relationships"] if r["country"] == country and (status is None or r["status"] == status)]


def active_by_institution(country):
    """One entry per foreign institution with confirmed active partnerships: what kind of work, not with whom."""
    out = {}
    for r in tracker_rows(country, "Active"):
        e = out.setdefault(r["foreign_institution"], {"institution": r["foreign_institution"], "group": r["group"],
                                                      "based_in": r.get("foreign_country", ""), "natures": set(),
                                                      "latest": "", "sources": []})
        e["natures"].add(r["type"])
        e["latest"] = max(e["latest"], r.get("last_evidence", ""))
        if r["sources"] and r["sources"][0] not in e["sources"]:
            e["sources"].append(r["sources"][0])
    for e in out.values():
        e["natures"] = sorted(e["natures"])
    return sorted(out.values(), key=lambda e: (GROUPS.index(e["group"]) if e["group"] in GROUPS else 9, e["institution"]))


def add_tracker_block(doc, country, registry, map_width=Cm(13.5), out_dir=None):
    """Competitive landscape from the verified tracker: confirmed active partnerships only,
    summarized by the nature of the collaboration rather than the partner hospital."""
    rows = tracker_rows(country, "Active")
    insts = active_by_institution(country)
    if not rows:
        p = doc.add_paragraph()
        p.add_run(f"CSI's partnerships tracker found no foreign health-system partnership in {country} that "
                  "could be confirmed as active from public sources.").italic = True
        return
    checked = max(r["last_checked"] for r in tracker_rows(country))
    png = partner_map(country, out_dir or ROOT / "output")
    if png:
        doc.add_picture(str(png), width=map_width)
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap = doc.add_paragraph()
        cr = cap.add_run(MAP_CAPTION.format(country=country, checked=checked))
        cr.italic = True
        cr.font.size = Pt(8)
        cr.font.color.rgb = GRAY

    t = doc.add_paragraph()
    t.paragraph_format.space_before = Pt(8)
    tr = t.add_run("Confirmed active partnerships by institution")
    tr.bold = True
    tr.font.color.rgb = DARK_RED
    table = doc.add_table(rows=1, cols=4)
    set_table_borders(table)
    for i, h in enumerate(("Institution", "Based in", "Nature of collaboration", "Latest evidence")):
        cell = table.rows[0].cells[i]
        set_cell_shading(cell, "D91F2C")
        r = cell.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for group in GROUPS:
        members = [e for e in insts if e["group"] == group]
        if not members:
            continue
        row = table.add_row()
        merged = row.cells[0].merge(row.cells[3])
        set_cell_shading(merged, "F6E3E4")
        gr = merged.paragraphs[0].add_run(group)
        gr.bold = True
        gr.font.size = Pt(9)
        gr.font.color.rgb = DARK_RED
        for e in members:
            cells = table.add_row().cells
            for i, text in enumerate((e["institution"], e["based_in"], ", ".join(e["natures"]), e["latest"])):
                run = cells[i].paragraphs[0].add_run(text)
                run.font.size = Pt(8.5)
                run.bold = i == 0
            add_citations(cells[3].paragraphs[0], sorted({registry.number(s) for s in e["sources"]}), registry)
    for row in table.rows:
        for i, w in enumerate((Cm(5.0), Cm(3.0), Cm(6.2), Cm(2.8))):
            row.cells[i].width = w
    note = doc.add_paragraph()
    nr = note.add_run("Only partnerships with dated evidence of activity in the last 24 months are listed. "
                      "Unclear and recently ended partnerships are in the CSI partnerships tracker.")
    nr.italic = True
    nr.font.size = Pt(8)
    nr.font.color.rgb = GRAY


def add_entries(doc, entries, sources, registry):
    """Competitive landscape: summary table, then entries grouped by type."""
    groups = []
    for e in entries:
        if e.get("group") not in groups:
            groups.append(e.get("group"))

    cap = doc.add_paragraph()
    cr = cap.add_run("Who is doing what")
    cr.bold = True
    cr.font.color.rgb = DARK_RED
    cap.paragraph_format.space_after = Pt(4)
    headers = ["Institution", "Partner(s) in country", "Relationship", "Status"]
    table = doc.add_table(rows=1, cols=4)
    set_table_borders(table)
    widths = [Cm(3.4), Cm(5.0), Cm(4.2), Cm(4.0)]
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        set_cell_shading(cell, "D91F2C")
        r = cell.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for g in groups:
        row = table.add_row()
        merged = row.cells[0].merge(row.cells[3])
        set_cell_shading(merged, "F6E3E4")
        gr = merged.paragraphs[0].add_run(g or "")
        gr.bold = True
        gr.font.size = Pt(9.5)
        gr.font.color.rgb = DARK_RED
        for e in (x for x in entries if x.get("group") == g):
            cells = table.add_row().cells
            for i, key in enumerate(("institution", "partner", "model", "status")):
                run = cells[i].paragraphs[0].add_run(e.get(key, ""))
                run.font.size = Pt(9.5)
                run.bold = key == "institution"
    for row in table.rows:
        for i, w in enumerate(widths):
            if i < len(row.cells):
                row.cells[i].width = w
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

    cited = False
    for g in groups:
        gp = doc.add_paragraph()
        gp.paragraph_format.space_before = Pt(6)
        gp.paragraph_format.space_after = Pt(4)
        grun = gp.add_run((g or "") + ":")
        grun.bold = True
        grun.underline = True
        for e in (x for x in entries if x.get("group") == g):
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            nr = p.add_run(e.get("institution", "") + ": ")
            nr.bold = True
            nr.font.color.rgb = DARK_RED
            cited |= add_cited_text(p, e.get("text", ""), sources, registry)
            if e.get("status"):
                sr = p.add_run(f" ({e['status']})")
                sr.italic = True
                sr.font.color.rgb = GRAY
    return cited


def add_manual_field(doc, label, value):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run(f"{label}\n")
    run.bold = True
    run.font.color.rgb = DARK_RED
    text = (value or "").strip()
    if not text:
        run2 = p.add_run(MANUAL_PLACEHOLDER)
        run2.bold = True
        run2.font.color.rgb = PLACEHOLDER_COLOR
        run2.font.highlight_color = WD_COLOR_INDEX.YELLOW
    else:
        p.add_run(text)


def cover_image_path(data, out_path):
    """Cover picture: explicit cover_image, else assets/covers/<Country>.jpg, else the red map."""
    if data.get("cover_image") and Path(data["cover_image"]).exists():
        return data["cover_image"]
    photo = SCRIPTS.parent / "assets" / "covers" / f"{data['country']}.jpg"
    if photo.exists():
        return str(photo)
    png = Path(out_path).with_name(f"{data['country'].replace(' ', '_')}_cover_map.png")
    if not png.exists():
        subprocess.run([sys.executable, str(SCRIPTS / "make_cover_map.py"), data["country"], str(png)], check=True)
    return str(png)


def add_cover_picture(doc, data, out_path):
    """Adds the cover picture and, for licensed photos, the required credit line."""
    doc.add_picture(cover_image_path(data, out_path), width=usable_width(doc))
    meta = SCRIPTS.parent / "assets" / "covers" / f"{data['country']}.json"
    if meta.exists() and not data.get("cover_image"):
        credit = json.loads(meta.read_text()).get("credit", "")
        if credit:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            p.paragraph_format.space_after = Pt(4)
            r = p.add_run(credit)
            r.font.size = Pt(7)
            r.font.color.rgb = GRAY


def build_toc(placeholder, headings):
    toc_title = placeholder.insert_paragraph_before()
    toc_title.paragraph_format.space_before = Pt(12)
    r = toc_title.add_run("Table of Contents")
    r.font.size = Pt(16)
    r.font.color.rgb = CEDARS_RED
    toc_title.paragraph_format.space_after = Pt(14)
    usable = usable_width(placeholder.part.document)
    for level, text, anchor in headings.items:
        p = placeholder.insert_paragraph_before()
        pf = p.paragraph_format
        pf.space_after = Pt(4 if level == 2 else 6)
        pf.space_before = Pt(0 if level == 2 else 8)
        pf.left_indent = Cm(0.6) if level == 2 else Cm(0)
        pf.tab_stops.add_tab_stop(usable, alignment=2, leader=WD_TAB_LEADER.DOTS)  # right-aligned
        add_internal_link(p, text, anchor, bold=(level == 1), italic=(level == 2))
        p.add_run("\t")
        add_field(p, f"PAGEREF {anchor} \\h", "")


# ---------------------------------------------------------------- build

def build_profile(data, out_path, registry):
    doc = Document()
    style_document(doc)
    update_fields_on_open(doc)
    add_page_number_footer(doc)
    headings = Headings()
    country = data["country"]
    research = data["research"]

    # Cover and table of contents share page 1 (house layout, from the analyst's hand edits)
    add_cover_title(doc, "Country Profile", country)
    add_cover_picture(doc, data, out_path)
    # Table of contents is filled in after the headings exist
    toc_placeholder = doc.add_paragraph()
    doc.add_page_break()

    headings.add(doc, "Country Overview", 1)
    add_rule(doc)
    for key, text in OVERVIEW_SECTIONS:
        if research["country_overview"].get(key):
            headings.add(doc, text, 2)
            add_section_body(doc, research["country_overview"][key], registry)

    headings.add(doc, f"{country} Health System", 1)
    add_rule(doc)
    for key, text in HEALTH_SECTIONS:
        if research["health_system"].get(key):
            headings.add(doc, text, 2)
            add_section_body(doc, research["health_system"][key], registry)

    rd = research.get("recent_developments", [])
    if rd:
        headings.add(doc, "Recent Developments", 1)
        add_rule(doc)
        for item in rd:
            summary = item.get("summary") or item.get("development") or ""
            sources = item.get("sources", [])
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            dr = p.add_run(f"{item['date']}  ")
            dr.bold = True
            dr.font.color.rgb = DARK_RED
            if item.get("headline"):
                p.add_run(item["headline"]).bold = True
                body = doc.add_paragraph()
                body.paragraph_format.space_after = Pt(12)
            else:
                body = p
            if not add_cited_text(body, summary, sources, registry) and sources:
                add_citations(body, sorted({registry.number(s) for s in sources}), registry)

    # Chart data used by the short summary gets numbers here too, so one sources document serves both.
    for chart in data.get("charts", []):
        for src in chart.get("sources", []):
            registry.number(src)

    doc.add_page_break()
    headings.add(doc, "CSI Assessment", 1)
    add_rule(doc)
    note = doc.add_paragraph()
    nr = note.add_run(
        "Everything below comes from Cedars-Sinai's internal data (patient referral records, finance, "
        "relationship history) and human judgment, not from the research agents. Fields left blank are "
        "marked and must be completed by the analyst before this profile is used."
    )
    nr.italic = True
    nr.font.size = Pt(10)
    nr.font.color.rgb = GRAY
    manual = data.get("csi_manual", {})
    for key, label in [
        ("patient_volume_and_revenue", "Patient Volume & Revenue (most recent FY)"),
        ("referral_sources", "Referral Sources"),
        ("relationship_history", "Relationship History"),
        ("complications", "Complications"),
        ("key_contacts", "Key Contacts"),
        ("opportunities", "Opportunities"),
        ("csi_recommendation", "CSI Recommendation"),
    ]:
        add_manual_field(doc, label, manual.get(key, ""))

    build_toc(toc_placeholder, headings)
    toc_placeholder._p.getparent().remove(toc_placeholder._p)
    doc.save(out_path)


def build_sources(data, out_path, registry):
    doc = Document()
    style_document(doc)
    add_page_number_footer(doc)
    k = doc.add_paragraph()
    kr = k.add_run("COUNTRY PROFILE & MARKET INTELLIGENCE")
    kr.bold = True
    kr.font.size = Pt(11)
    kr.font.color.rgb = GRAY
    t = doc.add_paragraph()
    tr = t.add_run(f"{data['country']}: Sources")
    tr.bold = True
    tr.font.size = Pt(26)
    tr.font.color.rgb = CEDARS_RED
    intro = doc.add_paragraph()
    ir = intro.add_run(
        f"Numbered to match the superscript citations in the {data['country']} country profile "
        f"(draft prepared {data.get('generated_date', '')}). Web sources were accessed in September 2026."
    )
    ir.italic = True
    ir.font.size = Pt(10)
    ir.font.color.rgb = GRAY
    add_rule(doc)
    for n, src in enumerate(registry.entries, 1):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(1.0)
        pf.first_line_indent = Cm(-1.0)
        pf.space_after = Pt(6)
        nr = p.add_run(f"{n}.\t")
        nr.bold = True
        nr.font.color.rgb = DARK_RED
        pf.tab_stops.add_tab_stop(Cm(1.0))
        text, url = format_reference(src)
        if text:
            p.add_run(text + (" " if url else ""))
        if url:
            add_external_link(p, url, url, color="1F4E99")
    doc.save(out_path)


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 generate_profile.py <input.json> <output.docx>")
    data = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2])
    registry = SourceRegistry()
    build_profile(data, str(out), registry)
    sources_out = out.with_name(f"{out.stem}_SOURCES.docx")
    build_sources(data, str(sources_out), registry)
    print(f"Wrote {out} and {sources_out} ({len(registry.entries)} sources)")


if __name__ == "__main__":
    main()
