#!/usr/bin/env python3
"""
Check a summary JSON against its finished profile before building the summary document.

Usage: python3 scripts/check_summary.py output/<country>_profile.json <summary.json>

Reports, and exits 1 on, any:
  - citation marker {{group.section:n}} that does not resolve to a source in the profile,
  - number in the summary text that does not appear anywhere in the profile text,
  - em or en dash,
  - bullet longer than 20 words.
Also prints the visible word count (target 380 to 450). Prints "issues: N".
"""
import json
import re
import sys

REF = re.compile(r"\{\{(\w+)\.(\w+):(\d+)\}\}")
NUM = re.compile(r"\d[\d,.]*\d|\d")
BULLETS = ("key_takeaways", "health_system", "market", "risks")


def strings(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k not in ("sources", "url", "charts", "resolution_log", "csi_manual"):
                yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)
    elif isinstance(o, str):
        yield o


def nums(text):
    return {n.replace(",", "").rstrip(".") for n in NUM.findall(REF.sub(" ", text))}


def main(profile_path, summary_path):
    profile = json.load(open(profile_path))
    summary = json.load(open(summary_path))
    r = profile["research"]
    issues = []
    profile_nums = set()
    for t in strings(profile):
        profile_nums |= nums(re.sub(r"\{\{[^}]+\}\}", " ", t))
    texts = []
    for tile in summary.get("at_a_glance", []):
        texts.append(("at_a_glance", f"{tile.get('value', '')} {tile.get('label', '')} {tile.get('cite', '')}"))
    for key in BULLETS:
        for b in summary.get(key, []):
            texts.append((key, b))
            words = len(REF.sub("", b).split())
            if words > 20:
                issues.append(f"{key}: bullet has {words} words (max 20): {b[:70]}")
    for item in summary.get("recent", []):
        texts.append(("recent", item.get("text", "")))
    texts.append(("country_background", summary.get("country_background", "")))
    visible = 0
    for where, t in texts:
        visible += len(REF.sub("", t).split())
        if re.search("[–—]", t):
            issues.append(f"{where}: contains an em or en dash")
        for group, key, n in REF.findall(t):
            try:
                sec = r["recent_developments"][int(key)] if group == "recent_developments" else r[group][key]
                sec["sources"][int(n) - 1]
            except (KeyError, IndexError, ValueError):
                issues.append(f"{where}: marker {{{{{group}.{key}:{n}}}}} does not resolve")
        missing = sorted(nums(t) - profile_nums)
        if missing:
            issues.append(f"{where}: numbers not found in the profile {missing}: {REF.sub('', t)[:70]}")
    for i in issues:
        print("ISSUE:", i)
    print(f"visible words: {visible} (target 380 to 450)")
    print(f"issues: {len(issues)}")
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
