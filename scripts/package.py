#!/usr/bin/env python3
"""Collect a country's finished deliverables into one folder and a zip.

Usage: python3 scripts/package.py India
Writes deliverables/<Country>/ and deliverables/<Country>_Brief_Package.zip.
File names are kept as generated, because the documents refer to each other by name.
"""
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(country):
    out = ROOT / "output"
    files = [
        out / f"{country}_Summary_DRAFT.docx",
        out / f"{country}_Profile_DRAFT.docx",
        out / f"{country}_Profile_DRAFT_SOURCES.docx",
        out / "Partnerships_Tracker.xlsx",
        out / f"{country}_partnerships_map.png",
    ]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        sys.exit(f"Missing: {', '.join(missing)}")
    folder = ROOT / "deliverables" / country
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    for f in files:
        shutil.copy2(f, folder / f.name)
    (folder / "README.txt").write_text(
        f"{country} country brief package\n\n"
        f"{country}_Summary_DRAFT.docx         Short visual summary (title page + about 4 pages)\n"
        f"{country}_Profile_DRAFT.docx         Full country profile\n"
        f"{country}_Profile_DRAFT_SOURCES.docx Numbered sources for both documents\n"
        f"Partnerships_Tracker.xlsx         Verified foreign health-system partnerships\n"
        f"{country}_partnerships_map.png       Partnerships by city (also inside both documents)\n\n"
        "In Word, click Yes if asked to update fields: it fills in the table-of-contents page numbers.\n"
    )
    zpath = ROOT / "deliverables" / f"{country}_Brief_Package.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.iterdir()):
            z.write(f, f"{country}_Brief_Package/{f.name}")
    print(f"Wrote {folder} ({len(files) + 1} files) and {zpath}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 scripts/package.py <Country>")
    main(sys.argv[1])
