#!/usr/bin/env python3
"""
Partnerships tracker: foreign health systems' partnerships in each country CSI
profiles. Only relationships that are active, or ended or last showed activity
within the past five years, are kept.

Data file: data/partnerships.json (source of truth; the Excel file is generated).

Each record: country, foreign_institution, foreign_country, group, indian_partner
(partner in the profiled country), type, description, status (Active | Ended |
Unclear), start, end, last_evidence (YYYY-MM), evidence, sources[], last_checked.

Commands:
  python3 scripts/tracker.py import <Country> <rows.json> [--checked YYYY-MM-DD]
      Replace that country's records with verified rows ({"relationships": [...]}).
  python3 scripts/tracker.py brief <Country> [out.json]
      Records a new profile should start from: that country's rows, plus every
      row for the same foreign institutions elsewhere (as leads, not facts).
  python3 scripts/tracker.py export [out.xlsx]
      Excel view (default output/Partnerships_Tracker.xlsx).
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "partnerships.json"
STATUSES = ["Active", "Unclear", "Ended"]
GROUP_ORDER = {"US academic medical centers": 0, "Other foreign health systems": 1}
STATUS_DEFS = {
    "Active": "A dated source from the last 24 months shows the partnership operating (current partner page, recent event, cohort, renewal or announcement).",
    "Ended": "A source says it ended, was terminated or not renewed, or a fixed term expired with no renewal. Only endings in the last five years are listed.",
    "Unclear": "Started or last active within five years, but no source settles whether it is still running. The 'Why' column says what is known and missing.",
}


def load():
    if DATA.exists():
        db = json.loads(DATA.read_text())
        if db.get("schema") == 2:
            return db
    return {"schema": 2, "scope": "Active, or ended or last active within the past five years", "relationships": []}


def save(db):
    DATA.parent.mkdir(exist_ok=True)
    db["relationships"].sort(key=sort_key)
    DATA.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n")


def sort_key(r):
    return (r["country"], STATUSES.index(r["status"]), GROUP_ORDER.get(r["group"], 2),
            r["foreign_institution"], r["indian_partner"])


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def import_rows(country, path, checked=None):
    rows = json.loads(Path(path).read_text())["relationships"]
    checked = checked or date.today().isoformat()
    db = load()
    db["relationships"] = [r for r in db["relationships"] if r["country"] != country]
    for r in rows:
        assert r["status"] in STATUSES, r
        r = {**r, "country": country, "last_checked": checked,
             "id": f"{slug(country)}--{slug(r['foreign_institution'])}--{slug(r['indian_partner'])}"}
        db["relationships"].append(r)
    save(db)
    counts = {s: sum(r["status"] == s and r["country"] == country for r in db["relationships"]) for s in STATUSES}
    print(f"{country}: {len(rows)} records imported {counts}")


def brief(country, out=None):
    db = load()
    mine = [r for r in db["relationships"] if r["country"] == country]
    insts = {r["foreign_institution"] for r in db["relationships"]}
    elsewhere = [r for r in db["relationships"] if r["country"] != country and r["foreign_institution"] in insts]
    payload = {"country": country, "as_of": date.today().isoformat(),
               "note": "Leads only. Re-confirm every status against primary sources before use.",
               "this_country": mine, "same_institutions_elsewhere": elsewhere}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if out:
        Path(out).write_text(text)
        print(f"Wrote {out}: {len(mine)} records for {country}, {len(elsewhere)} elsewhere")
    else:
        print(text)


def fmt_period(value):
    return value or ""


def export(out=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo

    db = load()
    rows = sorted(db["relationships"], key=sort_key)
    out = Path(out or ROOT / "output" / "Partnerships_Tracker.xlsx")
    F = "Arial"
    wb = Workbook()

    # --- Tracker (main sheet)
    ws = wb.active
    ws.title = "Tracker"
    headers = ["Status", "Country", "Foreign institution", "Based in", "Partner in country", "Type",
               "What it is", "Since", "Ended", "Latest evidence", "Why we say so", "Source"]
    ws.append(headers)
    fills = {"Active": "D9EAD3", "Unclear": "FCE8B2", "Ended": "E7E6E6"}
    for r in rows:
        src = r["sources"][0] if r["sources"] else {}
        who = src.get("publisher") or src.get("author", "")
        label = ", ".join(x for x in (who, src.get("date", "")) if x) or "Source"
        ws.append([r["status"], r["country"], r["foreign_institution"], r["foreign_country"], r["indian_partner"],
                   r["type"], r["description"], fmt_period(r.get("start")), fmt_period(r.get("end")),
                   r.get("last_evidence", ""), r["evidence"], label])
        row = ws.max_row
        if src.get("url"):
            ws.cell(row=row, column=12).hyperlink = src["url"]
        ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=fills[r["status"]])
    n = ws.max_row
    widths = [10, 9, 26, 14, 30, 22, 44, 9, 9, 10, 48, 28]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    thin = Side(style="thin", color="D9D9D9")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name=F, size=10, bold=(c.column in (1, 3)),
                          color="1F4E99" if c.column == 12 and c.hyperlink else None,
                          underline="single" if c.column == 12 and c.hyperlink else None)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = Border(bottom=thin)
    for c in ws[1]:
        c.font = Font(name=F, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="D91F2C")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "D2"
    tab = Table(displayName="Tracker", ref=f"A1:L{n}")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False)
    ws.add_table(tab)

    # --- All sources
    srcs = wb.create_sheet("All sources")
    srcs.append(["Foreign institution", "Partner in country", "Source", "Date", "Link"])
    for r in rows:
        for s in r["sources"]:
            srcs.append([r["foreign_institution"], r["indian_partner"],
                         " ".join(x for x in (s.get("author", ""), s.get("title", "")) if x), s.get("date", ""), s.get("url", "")])
            if s.get("url"):
                srcs.cell(row=srcs.max_row, column=5).hyperlink = s["url"]
    for i, w in enumerate([26, 30, 60, 14, 60], 1):
        srcs.column_dimensions[get_column_letter(i)].width = w
    for row in srcs.iter_rows():
        for c in row:
            c.font = Font(name=F, size=10, bold=c.row == 1, color="FFFFFF" if c.row == 1 else None)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if c.row == 1:
                c.fill = PatternFill("solid", fgColor="D91F2C")
    srcs.freeze_panes = "A2"

    # --- Read me (first tab)
    rm = wb.create_sheet("Read me", 0)
    rm["A1"] = "Foreign health-system partnerships tracker"
    rm["A1"].font = Font(name=F, bold=True, size=14, color="D91F2C")
    checked = max((r["last_checked"] for r in rows), default="")
    rm["A2"] = f"Scope: partnerships that are active, or ended or last active within the past five years. Last checked {checked}."
    rm["A2"].font = Font(name=F, size=10, italic=True, color="52514E")
    rm["A4"], rm["B4"], rm["C4"] = "Status", "Count", "What it means"
    for c in ("A4", "B4", "C4"):
        rm[c].font = Font(name=F, bold=True, color="FFFFFF")
        rm[c].fill = PatternFill("solid", fgColor="D91F2C")
    for i, s in enumerate(STATUSES, 5):
        rm[f"A{i}"] = s
        rm[f"A{i}"].fill = PatternFill("solid", fgColor=fills[s])
        rm[f"B{i}"] = f'=COUNTIF(Tracker!$A$2:$A${n},A{i})'
        rm[f"C{i}"] = STATUS_DEFS[s]
        for col in "ABC":
            rm[f"{col}{i}"].font = Font(name=F, size=10, bold=col == "A")
            rm[f"{col}{i}"].alignment = Alignment(wrap_text=True, vertical="top")
    rm["A9"] = "Total"
    rm["B9"] = "=SUM(B5:B7)"
    rm["A9"].font = rm["B9"].font = Font(name=F, size=10, bold=True)
    notes = [
        "Every row was researched and then checked by independent verifiers against primary sources "
        "(the institution's or partner's own pages, official releases, established news).",
        "Investors and owners (for example private equity buying hospitals) are not listed; this tracks health-system collaboration.",
        "The data lives in data/partnerships.json in the repository; this workbook is regenerated from it, so edits here are not saved back.",
    ]
    for i, t in enumerate(notes, 11):
        rm[f"A{i}"] = t
        rm[f"A{i}"].font = Font(name=F, size=10)
    rm.column_dimensions["A"].width = 14
    rm.column_dimensions["B"].width = 8
    rm.column_dimensions["C"].width = 110

    out.parent.mkdir(exist_ok=True)
    wb.save(out)
    print(f"Wrote {out} ({len(rows)} records)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "import" and len(a) >= 3:
        import_rows(a[1], a[2], a[a.index("--checked") + 1] if "--checked" in a else None)
    elif a[0] == "brief" and len(a) >= 2:
        brief(a[1], a[2] if len(a) > 2 else None)
    elif a[0] == "export":
        export(a[1] if len(a) > 1 else None)
    else:
        sys.exit(__doc__)
