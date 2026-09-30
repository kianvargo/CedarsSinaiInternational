#!/usr/bin/env python3
"""
Shared partnerships tracker: one verified record per (country, institution),
reused across country profiles so the same health systems aren't re-researched
from scratch each time.

Data file: data/partnerships.json

Commands:
  python3 scripts/tracker.py update <profile.json> [--verified YYYY-MM-DD]
      Merge a finished profile's competitive_landscape entries into the tracker
      (replaces that country's existing record for each institution).
  python3 scripts/tracker.py brief <Country> [out.json]
      Write what the tracker already knows that is relevant to a new profile:
      every record for that country, plus each monitored institution's records
      elsewhere. Research and verification agents read this first.
  python3 scripts/tracker.py export [out.xlsx]
      Excel view for people (default output/Partnerships_Tracker.xlsx).
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "partnerships.json"
STALE_DAYS = 90
MARKER = re.compile(r"\{\{(\d+)\}\}")

MONITORED = [
    "Mayo Clinic", "Cleveland Clinic", "Johns Hopkins", "Memorial Sloan Kettering",
    "MD Anderson Cancer Center", "Houston Methodist", "UCLA Health", "NewYork-Presbyterian",
    "UPMC", "Mass General Brigham", "Northwestern Medicine", "Mount Sinai Health System",
]


def load():
    if DATA.exists():
        return json.loads(DATA.read_text())
    return {"monitored_institutions": MONITORED, "stale_after_days": STALE_DAYS, "relationships": []}


def save(db):
    DATA.parent.mkdir(exist_ok=True)
    db["relationships"].sort(key=lambda r: (r["country"], r["group"], r["institution"]))
    DATA.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def update(profile_path, verified=None):
    profile = json.loads(Path(profile_path).read_text())
    country = profile["country"]
    cl = profile["research"]["health_system"]["competitive_landscape"]
    if not cl.get("entries"):
        sys.exit(f"{profile_path} has no competitive_landscape entries (older format); re-run the profile first")
    verified = verified or profile.get("generated_date") or date.today().isoformat()
    db = load()
    added = replaced = 0
    for e in cl["entries"]:
        nums = [int(n) for n in MARKER.findall(e.get("text", ""))]
        sources = [cl["sources"][n - 1] for n in dict.fromkeys(nums) if 1 <= n <= len(cl["sources"])]
        rec = {
            "id": f"{slug(country)}--{slug(e['institution'])}",
            "country": country,
            "group": e.get("group", ""),
            "institution": e["institution"],
            "partner": e.get("partner", ""),
            "model": e.get("model", ""),
            "status": e.get("status", ""),
            "summary": MARKER.sub("", e.get("text", "")).strip(),
            "last_verified": verified,
            "verification": "Country-profile pipeline: research, three independent verifiers, resolution; primary sources",
            "sources": sources,
        }
        old = [i for i, r in enumerate(db["relationships"]) if r["id"] == rec["id"]]
        if old:
            db["relationships"][old[0]] = rec
            replaced += 1
        else:
            db["relationships"].append(rec)
            added += 1
    save(db)
    print(f"{country}: {added} added, {replaced} replaced; tracker now has {len(db['relationships'])} records")


def brief(country, out=None):
    db = load()
    today = date.today()
    rel = []
    for r in db["relationships"]:
        if r["country"] == country or r["institution"] in db["monitored_institutions"]:
            age = (today - date.fromisoformat(r["last_verified"])).days
            rel.append({**r, "days_since_verified": age, "reuse_without_recheck": age <= db.get("stale_after_days", STALE_DAYS) and r["country"] == country})
    payload = {"country": country, "as_of": today.isoformat(), "stale_after_days": db.get("stale_after_days", STALE_DAYS),
               "monitored_institutions": db["monitored_institutions"], "relationships": rel}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if out:
        Path(out).write_text(text)
        print(f"Wrote {out}: {sum(r['country'] == country for r in rel)} records for {country}, {len(rel)} relevant in total")
    else:
        print(text)


def export(out=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo

    db = load()
    out = Path(out or ROOT / "output" / "Partnerships_Tracker.xlsx")
    wb = Workbook()
    font = "Arial"
    head_fill = PatternFill("solid", fgColor="D91F2C")
    head_font = Font(name=font, bold=True, color="FFFFFF")
    body = Font(name=font, size=10)
    wrap = Alignment(wrap_text=True, vertical="top")

    ws = wb.active
    ws.title = "Partnerships"
    headers = ["Country", "Group", "Institution", "Partner(s)", "Relationship", "Status",
               "Last verified", "Days since verified", "Needs re-check", "Summary", "Sources"]
    ws.append(headers)
    for r in db["relationships"]:
        srcs = "\n".join(f"{s.get('author', '')}: {s.get('url', '')}" for s in r["sources"])
        ws.append([r["country"], r["group"], r["institution"], r["partner"], r["model"], r["status"],
                   date.fromisoformat(r["last_verified"]), None, None, r["summary"], srcs])
    n = ws.max_row
    for row in range(2, n + 1):
        ws[f"H{row}"] = f"=TODAY()-G{row}"
        ws[f"I{row}"] = f'=IF(H{row}>\'About\'!$B$3,"Yes","No")'
        ws[f"G{row}"].number_format = "yyyy-mm-dd"
        ws[f"H{row}"].number_format = "0"
    widths = [10, 20, 24, 32, 30, 34, 13, 11, 10, 60, 60]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = body
            c.alignment = wrap
    for c in ws[1]:
        c.font = head_font
        c.fill = head_fill
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.freeze_panes = "D2"
    tab = Table(displayName="Partnerships", ref=f"A1:K{n}")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=True)
    ws.add_table(tab)

    # Coverage: monitored institutions x countries covered so far
    cov = wb.create_sheet("Coverage")
    countries = sorted({r["country"] for r in db["relationships"]})
    cov.append(["Institution"] + countries)
    for inst in db["monitored_institutions"]:
        cov.append([inst])
        row = cov.max_row
        for j, country in enumerate(countries, 2):
            hits = [r for r in db["relationships"] if r["country"] == country and inst.lower() in r["institution"].lower()]
            cov.cell(row=row, column=j, value=hits[0]["status"] if hits else "Not in tracker")
    cov.column_dimensions["A"].width = 28
    for j in range(2, len(countries) + 2):
        cov.column_dimensions[get_column_letter(j)].width = 48
    for row in cov.iter_rows():
        for c in row:
            c.font = body
            c.alignment = wrap
    for c in cov[1]:
        c.font = head_font
        c.fill = head_fill
    cov.freeze_panes = "B2"

    about = wb.create_sheet("About")
    about["A1"] = "Cedars-Sinai International partnerships tracker"
    about["A1"].font = Font(name=font, bold=True, size=14, color="D91F2C")
    about["A3"] = "Re-check after (days)"
    about["B3"] = db.get("stale_after_days", STALE_DAYS)
    about["B3"].font = Font(name=font, color="0000FF")
    about["C3"] = "Input: edit this number to change when a record is flagged in 'Needs re-check'."
    notes = [
        "Source of truth is data/partnerships.json in the repository; this workbook is regenerated from it "
        "(python3 scripts/tracker.py export). Edits made here are not saved back.",
        "Each record was verified by the country-profile pipeline (research, three independent verifiers, "
        "resolution) against primary sources on the 'Last verified' date.",
        "Status says only what sources support. 'Current status not confirmed' means the start is documented "
        "but no public evidence from recent years shows the relationship is active or has ended.",
        "Coverage tab: status of each monitored US institution in each country profiled so far (filled from the data file when exported).",
    ]
    for i, t in enumerate(notes, 5):
        about[f"A{i}"] = t
    for row in about.iter_rows():
        for c in row:
            if c.row != 1:
                c.font = Font(name=font, size=10, color=c.font.color.rgb if c.coordinate == "B3" else None)
    about.column_dimensions["A"].width = 110
    about.column_dimensions["C"].width = 70

    wb.move_sheet("About", offset=-2)
    out.parent.mkdir(exist_ok=True)
    wb.save(out)
    print(f"Wrote {out} ({len(db['relationships'])} records)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    cmd = args[0]
    if cmd == "update" and len(args) >= 2:
        v = args[args.index("--verified") + 1] if "--verified" in args else None
        update(args[1], v)
    elif cmd == "brief" and len(args) >= 2:
        brief(args[1], args[2] if len(args) > 2 else None)
    elif cmd == "export":
        export(args[1] if len(args) > 1 else None)
    else:
        sys.exit(__doc__)
