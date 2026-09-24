#!/usr/bin/env python3
"""Fetch a web page and print its visible text, optionally only lines matching keywords.

Usage:
  python3 fetch_text.py URL                      # first 6000 chars of visible text
  python3 fetch_text.py URL -k india mou 2024    # only lines containing any keyword (case-insensitive), with 1 line of context
  python3 fetch_text.py URL -n 12000             # change the character cap
"""
import argparse
import re
import subprocess
import sys
from html.parser import HTMLParser

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


class TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        elif tag in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.parts.append(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("-k", "--keywords", nargs="*", default=[])
    ap.add_argument("-n", "--max-chars", type=int, default=6000)
    args = ap.parse_args()

    res = subprocess.run(
        ["curl", "-sL", "--max-time", "30", "-A", UA, "-w", "\n__HTTP_STATUS__%{http_code}", args.url],
        capture_output=True, text=True, errors="replace",
    )
    body, _, status = res.stdout.rpartition("\n__HTTP_STATUS__")
    print(f"[HTTP {status or 'error'}] {args.url}")
    if not status.startswith("2"):
        print("Fetch failed or blocked by the site. Try the institution's press release on a newswire (PR Newswire, Business Wire, EurekAlert) or another official page.")
        sys.exit(1)

    if "%PDF" in body[:10]:
        print("This is a PDF; download with curl -o and use pdftotext if available.")
        sys.exit(1)

    ex = TextExtractor()
    ex.feed(body)
    text = re.sub(r"[ \t]+", " ", "".join(ex.parts))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    if args.keywords:
        kws = [k.lower() for k in args.keywords]
        keep = set()
        for i, ln in enumerate(lines):
            if any(k in ln.lower() for k in kws):
                keep.update({i - 1, i, i + 1})
        out = "\n".join(lines[i] for i in sorted(keep) if 0 <= i < len(lines))
        if not out:
            print("No lines matched the keywords.")
    else:
        out = "\n".join(lines)
    print(out[: args.max_chars])


if __name__ == "__main__":
    main()
