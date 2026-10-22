#!/usr/bin/env python3
"""
US dollar equivalents for monetary values in the country drafts.

Rates: data/fx_rates.json (units of local currency per US dollar, one reference date).
  python3 scripts/fx.py AUD 270.5e9         -> US$190 billion
  python3 scripts/fx.py NZD 34.2e9 --short  -> US$19.4 bn
Values are rounded to three significant figures.
"""
import json
import math
import sys
from pathlib import Path

RATES = json.loads((Path(__file__).resolve().parent.parent / "data" / "fx_rates.json").read_text())["rates"]


def sig3(x):
    if x == 0:
        return 0
    return round(x, 2 - int(math.floor(math.log10(abs(x)))))


def usd(currency, value, short=False):
    v = value / RATES[currency]["per_usd"]
    for size, long_name, short_name in ((1e12, "trillion", "tn"), (1e9, "billion", "bn"), (1e6, "million", "m")):
        if v >= size:
            n = sig3(v / size)
            if n >= 1000:  # rounding pushed it to the next scale
                continue
            num = f"{n:,.2f}".rstrip("0").rstrip(".")
            return f"US${num} {short_name if short else long_name}"
    n = sig3(v)
    return f"US${n:,.0f}" if n >= 10 else f"US${n:,.2f}".rstrip("0").rstrip(".")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    print(usd(args[0], float(args[1]), "--short" in sys.argv))
