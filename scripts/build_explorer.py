#!/usr/bin/env python3
"""
Build the interactive country explorer: a world map where hovering or searching
lifts a country out of the map and opens its profile in a side panel.

Usage: python3 scripts/build_explorer.py
Reads output/<country>_profile.json (and <country>_summary.json, data/partnerships.json
when present) and writes explorer/index.html. Each country's finished documents are
copied to explorer/files/ so the page can offer them for download.
Re-run it after a new profile is built and the new country lights up on the map.
"""
import base64
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "explorer" / "index.html"
TEMPLATE = ROOT / "scripts" / "explorer_template.html"

FILES = OUT.parent / "files"
# What each brief offers for download, in panel order. Missing files are skipped.
DOWNLOADS = [
    ("Short visual summary", "Word", "output/{c}_Summary_DRAFT.docx"),
    ("Full country profile", "Word", "output/{c}_Profile_DRAFT.docx"),
    ("Sources", "Word", "output/{c}_Profile_DRAFT_SOURCES.docx"),
    ("Partnerships tracker", "Excel", "output/Partnerships_Tracker.xlsx"),
    ("Partnerships map", "PNG", "output/{c}_partnerships_map.png"),
    ("Everything, zipped", "ZIP", "deliverables/{c}_Brief_Package.zip"),
]

CITE = re.compile(r"\{\{[^}]*\}\}")


def strip(text):
    return re.sub(r"\s+", " ", CITE.sub("", text or "")).strip()


def first_sentences(text, n=3):
    parts = re.split(r"(?<=[.!?])\s+", strip(text))
    return " ".join(parts[:n])


def geometry():
    src = json.loads((ROOT / "assets" / "ne_110m_countries.geojson").read_text())

    def rnd(c):
        if isinstance(c[0], (int, float)):
            return [round(c[0], 2), round(c[1], 2)]
        return [rnd(x) for x in c]

    feats = []
    for f in src["features"]:
        p = f["properties"]
        if p["ADMIN"] == "Antarctica":
            continue
        g = f["geometry"]
        feats.append({"type": "Feature", "properties": {"name": p["ADMIN"]},
                      "geometry": {"type": g["type"], "coordinates": rnd(g["coordinates"])}})
    return {"type": "FeatureCollection", "features": feats}


def partnerships(country):
    path = ROOT / "data" / "partnerships.json"
    if not path.exists():
        return []
    rows = [r for r in json.loads(path.read_text())["relationships"] if r.get("country") == country]
    order = {"Active": 0, "Unclear": 1, "Ended": 2}
    rows.sort(key=lambda r: (order.get(r["status"], 3), r["foreign_institution"]))
    return [{"who": r["foreign_institution"], "from": r["foreign_country"], "partner": r.get("indian_partner") or r.get("partner", ""),
             "type": r["type"], "status": r["status"], "what": r["description"]} for r in rows]


def downloads(country, partners):
    out = []
    for label, kind, pattern in DOWNLOADS:
        src = ROOT / pattern.format(c=country)
        if not src.exists() or ("Tracker" in src.name and not partners):
            continue
        FILES.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, FILES / src.name)
        # claude.ai only serves web file types, so the published page fetches a base64 text copy.
        (FILES / (src.name + ".b64.txt")).write_bytes(base64.b64encode(src.read_bytes()))
        out.append({"label": label, "kind": kind, "file": "files/" + src.name, "size": src.stat().st_size})
    return out


def profile(path):
    d = json.loads(path.read_text())
    country = d["country"]
    r = d["research"]
    demo = r["country_overview"]["demographics"]
    facts = [{"label": f["label"], "value": strip(f["value"])} for f in demo.get("facts", [])]
    rec = {
        "country": country,
        "date": d.get("generated_date", ""),
        "facts": facts,
        "background": first_sentences(demo.get("narrative", ""), 4),
        "sections": [k.replace("_", " ").capitalize() for k in list(r["country_overview"]) + list(r["health_system"])],
        "recent": [{"date": x.get("date", ""), "text": strip(x.get("headline") or first_sentences(x.get("summary", ""), 1))}
                   for x in r.get("recent_developments", [])][:5],
        "partners": partnerships(country),
        "verified": "resolution_log" in d and any("{{" in f["value"] for f in demo.get("facts", [])),
    }
    rec["downloads"] = downloads(country, rec["partners"])
    summ = path.with_name(path.name.replace("_profile", "_summary"))
    if summ.exists():
        s = json.loads(summ.read_text())
        rec["background"] = strip(s.get("country_background", "")) or rec["background"]
        rec["tiles"] = [{"value": t["value"], "label": t["label"]} for t in s.get("at_a_glance", [])]
        rec["takeaways"] = [strip(x) for x in s.get("key_takeaways", [])]
        rec["opportunities"] = [strip(x) for x in s.get("opportunities", [])]
        rec["risks"] = [strip(x) for x in s.get("risks", [])]
    return rec


def main():
    if FILES.exists():
        shutil.rmtree(FILES)
    profiles = {}
    for p in sorted((ROOT / "output").glob("*_profile.json")):
        rec = profile(p)
        profiles[rec["country"]] = rec
    html = TEMPLATE.read_text()
    html = html.replace("/*__GEO__*/null", json.dumps(geometry(), separators=(",", ":")))
    html = html.replace("/*__PROFILES__*/null", json.dumps(profiles, ensure_ascii=False, separators=(",", ":")))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html)
    (OUT.parent / "publish_files.json").write_text(json.dumps(
        {f"files/{f.name}": str(f.relative_to(ROOT)) for f in sorted(FILES.glob("*.b64.txt"))}, indent=1) + "\n")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB) with {len(profiles)} profiles: {', '.join(profiles)}")


if __name__ == "__main__":
    main()
