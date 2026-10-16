#!/usr/bin/env python3
"""
Guard for the polish pass (AI-signal cleanup + humanizer): wording may change, facts may not.

Usage: python3 scripts/check_polish.py <before.json> <after.json>
Works on profile JSON and summary JSON. Exits 1, listing every problem, if the polished file:
  - changed its structure (keys, list lengths, chart data, CSI fields),
  - changed any source object,
  - added, dropped or altered any number in a text field, or
  - added, dropped, reordered or moved any citation marker ({{n}} or {{group.section:n}}).
"""
import json
import re
import sys
from collections import Counter

NUM = re.compile(r"\d[\d,.]*\d|\d")
MARK = re.compile(r"\{\{[^}]+\}\}")
SKIP_TEXT_KEYS = {"url", "date", "generated_date"}


def numbers(text):
    return Counter(n.replace(",", "").rstrip(".") for n in NUM.findall(MARK.sub(" ", text)))


def walk(a, b, path, problems):
    if type(a) is not type(b):
        problems.append(f"{path}: type changed")
    elif isinstance(a, dict):
        if set(a) != set(b):
            problems.append(f"{path}: keys changed {sorted(set(a) ^ set(b))}")
        for k in set(a) & set(b):
            if k in ("sources", "charts", "csi_manual", "resolution_log") and a[k] != b[k]:
                problems.append(f"{path}.{k}: must not change in the polish pass")
            elif k not in ("sources", "charts", "csi_manual", "resolution_log"):
                walk(a[k], b[k], f"{path}.{k}", problems)
    elif isinstance(a, list):
        if len(a) != len(b):
            problems.append(f"{path}: list length {len(a)} -> {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", problems)
    elif isinstance(a, str):
        if path.rsplit(".", 1)[-1] in SKIP_TEXT_KEYS or path.endswith(".label"):
            if a != b:
                problems.append(f"{path}: must not change")
            return
        if MARK.findall(a) != MARK.findall(b):
            problems.append(f"{path}: citation markers changed {MARK.findall(a)} -> {MARK.findall(b)}")
        if numbers(a) != numbers(b):
            lost, added = numbers(a) - numbers(b), numbers(b) - numbers(a)
            problems.append(f"{path}: numbers changed (removed {dict(lost)}, added {dict(added)})")
    elif a != b:
        problems.append(f"{path}: value changed {a!r} -> {b!r}")


def main(before, after):
    problems = []
    walk(json.load(open(before)), json.load(open(after)), "$", problems)
    for p in problems:
        print("PROBLEM:", p)
    print(f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
