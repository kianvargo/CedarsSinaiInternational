#!/usr/bin/env python3
"""
Freshness and labeling checks for country profile metrics.

World Bank health indicators lag their upstream sources (workforce and beds are often two to ten
years old), while demographics are current. This script finds the stale ones so a newer source can
be used, and checks that every numeric fact says what it measures.

Usage:
  python3 scripts/freshness.py wb <worldbank.json> [--out report.json] [--year 2026]
      Before research. Reads the file written by scripts/worldbank.py and lists, for the country,
      the latest year of each indicator, its age, and whether it is stale. Give the report to the
      research agent: every STALE metric must be looked up in a tier 1 or tier 2 source first.

  python3 scripts/freshness.py check <profile.json> [--year 2026] [--lenient]
      After resolution. Reads every fact in the profile and fails (exit 1) when
        - a metric with an age limit is older than the limit and the fact neither comes from a
          tier 1 or 2 source ("tier": 1 or 2) nor records the search ("newer_checked"), or
        - a numeric fact has no "basis" (what is measured, scope, definition).
      --lenient only prints the problems (for profiles made before these fields existed).

Source tiers (the "tier" field on a fact; see SKILL.md):
  1 national statistics office or health ministry
  2 OECD (members) or WHO Global Health Observatory / Global Health Expenditure Database
  3 World Bank (baseline for demographics and economy; fallback for health metrics)

Optional fact fields: "basis" (printed under the label), "tier" (1, 2 or 3), and "newer_checked"
(one line saying which tier 1 or 2 sources were searched and that none had a newer value).
"""
import json
import re
import sys
from datetime import date

# (regex on the metric name, group, maximum age in years)
RULES = [
    (r"physician|doctor|practitioner|nurse|midwi|pharmacist|dentist|hospital bed|beds per", "workforce and beds", 2),
    (r"health expenditure|health spending|out-of-pocket|government share|public funding|spending per", "health spending", 3),
    (r"population|gdp|urban|fertility|life expectancy|aged 65|ages 65", "demographics and economy", 2),
]

# What to search before accepting a stale World Bank value
WHERE_TO_LOOK = {
    "workforce and beds": "national health workforce register or ministry; OECD Health Statistics (members); WHO Global Health Observatory",
    "health spending": "national health accounts (statistics office or ministry); OECD Health Statistics (members); WHO Global Health Expenditure Database",
    "demographics and economy": "national statistics office; IMF World Economic Outlook",
}

WB_NAMES = {  # indicator code prefix -> metric name matched against RULES
    "SP.POP": "population", "SP.URB": "urban population", "SP.DYN.LE": "life expectancy",
    "SP.DYN.TF": "fertility", "NY.GDP": "gdp", "SH.XPD": "health expenditure",
    "SH.MED.PHYS": "physicians", "SH.MED.NUMW": "nurses", "SH.MED.BEDS": "hospital beds",
}

YEAR = re.compile(r"(?<!\d)((?:19|20)\d\d)(?:\s*[-/]\s*(\d\d))?(?!\d)")
MARK = re.compile(r"\{\{[^}]+\}\}")


def rule_for(name):
    low = name.lower()
    for pattern, group, limit in RULES:
        if re.search(pattern, low):
            return group, limit
    return None, None


def first_year(text):
    """Year of the lead value; a financial year such as 2024-25 counts as 2025."""
    m = YEAR.search(MARK.sub("", text))
    if not m:
        return None
    year = int(m.group(1))
    if m.group(2):
        year = (year // 100) * 100 + int(m.group(2))
        if year < int(m.group(1)):
            year += 100
    return year


def wb_report(path, this_year):
    data = json.load(open(path))
    rows = []
    for code, series in data["series"].items():
        points = series.get("points") or []
        key = next((v for k, v in WB_NAMES.items() if code.startswith(k)), series["name"])
        group, limit = rule_for(key + " " + series["name"])
        if not points:
            rows.append({"indicator": code, "name": series["name"], "latest_year": None, "age": None,
                         "limit": limit, "status": "NO DATA", "group": group})
            continue
        year, value = points[-1]
        age = this_year - year
        status = "STALE" if limit is not None and age > limit else "ok"
        rows.append({"indicator": code, "name": series["name"], "latest_year": year, "value": value,
                     "age": age, "limit": limit, "status": status, "group": group,
                     "look_in_first": WHERE_TO_LOOK.get(group) if status != "ok" else None})
    return {"country": data["country"], "as_of_year": this_year, "metrics": rows}


def walk_facts(research):
    for group, sections in research.items():
        if not isinstance(sections, dict):
            continue
        for key, section in sections.items():
            if isinstance(section, dict):
                for fact in section.get("facts", []) or []:
                    yield f"{group}.{key}", fact


def check_profile(path, this_year):
    research = json.load(open(path))["research"]
    problems, facts_seen, numeric = [], 0, 0
    for where, fact in walk_facts(research):
        facts_seen += 1
        label, value = fact.get("label", ""), MARK.sub("", str(fact.get("value", "")))
        if re.search(r"\d", value):
            numeric += 1
            if not fact.get("basis"):
                problems.append(f"{where}: '{label}' has no basis (what is measured, scope, definition)")
        group, limit = rule_for(label)
        year = first_year(value)
        if limit is None or year is None:
            continue
        age = this_year - year
        if age > limit and fact.get("tier") not in (1, 2) and not fact.get("newer_checked"):
            problems.append(f"{where}: '{label}' is {year} ({age} years old, limit {limit} for {group}); "
                            f"search {WHERE_TO_LOOK[group]} and set tier or newer_checked")
    return problems, facts_seen, numeric


def main(argv):
    this_year = date.today().year
    if "--year" in argv:
        i = argv.index("--year"); this_year = int(argv[i + 1]); del argv[i:i + 2]
    lenient = "--lenient" in argv
    argv = [a for a in argv if a != "--lenient"]
    out = None
    if "--out" in argv:
        i = argv.index("--out"); out = argv[i + 1]; del argv[i:i + 2]
    if len(argv) != 2 or argv[0] not in ("wb", "check"):
        sys.exit(__doc__)
    mode, path = argv
    if mode == "wb":
        report = wb_report(path, this_year)
        for r in report["metrics"]:
            if r["limit"] is None and r["status"] == "ok":
                continue
            yr = r["latest_year"] if r["latest_year"] else "-"
            print(f"{r['status']:8} {r['name'][:62]:62} latest {yr}  age {r['age']}  limit {r['limit']}")
        stale = [r for r in report["metrics"] if r["status"] == "STALE"]
        print(f"{len(stale)} stale of {len(report['metrics'])} World Bank indicators for {report['country']}")
        if out:
            json.dump(report, open(out, "w"), indent=1)
            print(f"Wrote {out}")
        return 0
    problems, facts_seen, numeric = check_profile(path, this_year)
    for p in problems:
        print("PROBLEM:", p)
    print(f"{facts_seen} facts ({numeric} numeric), {len(problems)} problem(s)")
    return 0 if lenient or not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
