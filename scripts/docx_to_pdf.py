#!/usr/bin/env python3
"""
Export Word documents to PDF next to them (same base name).

Usage: python3 scripts/docx_to_pdf.py output/<Country>_Profile_DRAFT.docx [more.docx ...]

Tries, in order:
  1. LibreOffice (soffice --headless --convert-to pdf): closest to Word's own layout.
  2. Fallback when LibreOffice is unavailable or broken: convert to HTML (mammoth) and print to PDF
     with headless Chromium (Playwright). Text, headings, tables, images and links come through, but
     pagination and some styling differ from Word, so check the result and prefer a Word export
     (File > Save As > PDF) for formal distribution.
Requires for the fallback: pip install mammoth playwright (and a Chromium browser).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CSS = """
@page { size: Letter; margin: 0.75in; }
body { font-family: Arial, Helvetica, sans-serif; font-size: 10.5pt; line-height: 1.4; color: #282829; }
h1 { color: #B31822; font-size: 18pt; border-bottom: 1.5px solid #D91F2C; padding-bottom: 3px; margin-top: 18pt; break-after: avoid; }
h2 { color: #B31822; font-size: 13pt; margin-top: 14pt; break-after: avoid; }
h3 { font-size: 11pt; break-after: avoid; }
p { margin: 0 0 7pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9pt; }
td, th { border: 1px solid #D9D9D9; padding: 3pt 5pt; vertical-align: top; }
tr { break-inside: avoid; }
img { max-width: 100%; height: auto; display: block; margin: 6pt auto; }
sup { font-size: 7pt; }
a { color: #B31822; text-decoration: none; }
.keep { display: inline-block; width: 100%; break-inside: avoid; }
p:has(> img) { break-inside: avoid; }
body > p:first-child { font-size: 20pt; color: #CC0000; margin-top: 30pt; }
"""


def libreoffice(docx, outdir):
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return False
    target = outdir / (docx.stem + ".pdf")
    target.unlink(missing_ok=True)  # LibreOffice can exit 0 without writing; only trust a fresh file
    with tempfile.TemporaryDirectory() as profile:
        r = subprocess.run([exe, "--headless", "--norestore", f"-env:UserInstallation=file://{profile}",
                            "--convert-to", "pdf", "--outdir", str(outdir), str(docx)],
                           capture_output=True, text=True, timeout=300)
    return r.returncode == 0 and target.exists() and target.stat().st_size > 0


def chromium(docx, pdf):
    import mammoth
    from playwright.sync_api import sync_playwright
    with open(docx, "rb") as f:
        body = mammoth.convert_to_html(f).value
    # Chromium ignores "keep with next" when printing, so glue each label or heading to the block
    # after it (a chart, table or first paragraph) in one unbreakable wrapper.
    body = re.sub(r"(<p><strong>[^<]{1,160}</strong></p>|<h[1-3][^>]*>(?:(?!</h[1-3]>).)*</h[1-3]>)\s*(<p><img [^>]*></p>|<table>.*?</table>|<p>.*?</p>)",
                  r'<div class="keep">\1\2</div>', body, flags=re.S)
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as t:
        t.write(html)
    exe = os.environ.get("CHROMIUM_PATH") or ("/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None)
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        pg = b.new_page()
        pg.goto(Path(t.name).as_uri())
        pg.emulate_media(media="print")
        pg.pdf(path=str(pdf), format="Letter", print_background=True, prefer_css_page_size=True,
               display_header_footer=True, header_template="<span></span>",
               footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#6E6E6E'>Cedars-Sinai International &nbsp; <span class='pageNumber'></span></div>",
               margin={"top": "0.75in", "bottom": "0.8in", "left": "0.75in", "right": "0.75in"})
        b.close()
    os.unlink(t.name)


def main(paths):
    for p in paths:
        docx = Path(p).resolve()
        pdf = docx.with_suffix(".pdf")
        if libreoffice(docx, docx.parent):
            print(f"{pdf.name}: LibreOffice")
        else:
            chromium(docx, pdf)
            print(f"{pdf.name}: Chromium fallback (check layout; prefer a Word export for distribution)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
