#!/usr/bin/env python3
"""
Pull the standard World Bank indicators for a profile in one go, so research agents do not
spend effort fetching them page by page.

Usage: python3 scripts/worldbank.py <ISO3> [comparators ISO3 ...] [--out file.json]
  e.g. python3 scripts/worldbank.py ESP PRT FRA ITA DEU GBR USA OED --out <scratchpad>/spain_wb.json

Writes, for the country, every year 2010 onward of each indicator below, and for comparators the
latest value of each; every series carries its API source URL and "last updated" date, ready to
cite. Uses the World Bank Indicators API (api.worldbank.org/v2), which needs no key.
"""
import json
import sys
import time
import urllib.request

INDICATORS = {
    "SP.POP.TOTL": "Population, total",
    "SP.POP.65UP.TO.ZS": "Population ages 65 and above (% of total population)",
    "SP.URB.TOTL.IN.ZS": "Urban population (% of total population)",
    "SP.DYN.LE00.IN": "Life expectancy at birth, total (years)",
    "SP.DYN.TFRT.IN": "Fertility rate, total (births per woman)",
    "NY.GDP.MKTP.PP.CD": "GDP, PPP (current international $)",
    "NY.GDP.PCAP.PP.CD": "GDP per capita, PPP (current international $)",
    "SH.XPD.CHEX.GD.ZS": "Current health expenditure (% of GDP)",
    "SH.XPD.CHEX.PC.CD": "Current health expenditure per capita (current US$)",
    "SH.XPD.OOPC.CH.ZS": "Out-of-pocket expenditure (% of current health expenditure)",
    "SH.XPD.GHED.CH.ZS": "Domestic general government health expenditure (% of current health expenditure)",
    "SH.MED.PHYS.ZS": "Physicians (per 1,000 people)",
    "SH.MED.NUMW.P3": "Nurses and midwives (per 1,000 people)",
    "SH.MED.BEDS.ZS": "Hospital beds (per 1,000 people)",
    "SH.DTH.NCOM.ZS": "Cause of death, by non-communicable diseases (% of total)",
}
API = "https://api.worldbank.org/v2/country/{c}/indicator/{i}?format=json&per_page=500&date=2010:2026"


def get(url, tries=4):
    for t in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except Exception:
            if t == tries - 1:
                raise
            time.sleep(3 * (t + 1))


def fetch(country, ind):
    url = API.format(c=country, i=ind)
    meta, rows = get(url)
    points = sorted((int(r["date"]), r["value"]) for r in rows or [] if r["value"] is not None)
    return {"indicator": ind, "name": INDICATORS[ind], "url": url.split("&per_page")[0],
            "last_updated": meta.get("lastupdated"), "points": points}


def latest(countries, ind):
    """Latest non-empty value per comparator, in one request."""
    url = API.format(c=";".join(countries), i=ind)
    _, rows = get(url)
    out = {}
    for r in sorted(rows or [], key=lambda r: r["date"], reverse=True):
        c = r["countryiso3code"] or r["country"]["id"]
        if r["value"] is not None and c not in out:
            out[c] = [int(r["date"]), r["value"]]
    return {"values": out, "url": url.split("&per_page")[0]}


def main(args):
    out = None
    if "--out" in args:
        i = args.index("--out"); out = args[i + 1]; args = args[:i] + args[i + 2:]
    country, comps = args[0].upper(), [a.upper() for a in args[1:]]
    data = {"country": country, "series": {}, "comparators": {}}
    for ind in INDICATORS:
        data["series"][ind] = fetch(country, ind)
        if comps:
            data["comparators"][ind] = latest(comps, ind)
    text = json.dumps(data, indent=1)
    if out:
        open(out, "w").write(text); print(f"Wrote {out}")
    else:
        print(text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
