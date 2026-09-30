#!/usr/bin/env python3
"""
Find a reusable landmark photo for a country's cover on Wikimedia Commons.

Usage:
  python3 scripts/fetch_cover_photo.py China                      # uses the default landmark below
  python3 scripts/fetch_cover_photo.py Brazil --landmark "Christ the Redeemer Rio"
  python3 scripts/fetch_cover_photo.py India --file path/to/photo.jpg   # use a supplied photo

Writes assets/covers/<Country>.jpg and <Country>.json (credit line). Only files
whose license allows reuse are accepted: public domain, CC0, CC BY or CC BY-SA
(the last two need the credit line, which the generators print under the photo).
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
COVERS = ROOT / "assets" / "covers"
API = "https://commons.wikimedia.org/w/api.php"
UA = "CSI-country-profile/1.0 (Cedars-Sinai International research briefs)"
OK_LICENSES = re.compile(r"^(public domain|pd|cc0|cc[- ]by(-sa)?[- ][0-9.]+)", re.I)

DEFAULT_LANDMARKS = {
    "China": "Great Wall of China Mutianyu",
    "Vietnam": "Ha Long Bay",
    "Kuwait": "Kuwait Towers",
    "Qatar": "Doha skyline West Bay",
    "Uzbekistan": "Registan Samarkand",
    "Paraguay": "Palacio de los López Asunción",
    "Brazil": "Christ the Redeemer Rio de Janeiro",
    "Mexico": "Chichen Itza El Castillo",
    "Saudi Arabia": "Kingdom Centre Riyadh",
    "United Arab Emirates": "Sheikh Zayed Grand Mosque",
    "Indonesia": "Borobudur",
    "Philippines": "Manila skyline",
    "Japan": "Mount Fuji",
    "South Korea": "Gyeongbokgung",
    "Egypt": "Pyramids of Giza",
    "Turkey": "Hagia Sophia",
    "Kazakhstan": "Baiterek Astana",
    "Nigeria": "Lagos skyline",
    "Kenya": "Nairobi skyline",
}


def fetch(url, timeout=60):
    """GET with backoff: Wikimedia answers 429 when requests come too fast."""
    for wait in (0, 5, 15, 45):
        time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
    raise SystemExit("Wikimedia is rate-limiting requests; try again in a few minutes.")


def api(params):
    return json.loads(fetch(API + "?" + urllib.parse.urlencode({**params, "format": "json"}), timeout=30))


def clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def save(country, img, credit):
    COVERS.mkdir(parents=True, exist_ok=True)
    img = img.convert("RGB")
    w, h = img.size
    target = 16 / 9  # crop to a consistent landscape frame
    if w / h > target:
        nw = int(h * target)
        img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    elif w / h < target:
        nh = int(w / target)
        img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    out = COVERS / f"{country}.jpg"
    img.save(out, quality=90)
    (COVERS / f"{country}.json").write_text(json.dumps(credit, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {out} ({img.size[0]}x{img.size[1]}); credit: {credit.get('credit') or '(supplied by CSI)'}")


def from_file(country, path, credit_text=""):
    save(country, Image.open(path), {"source": "Supplied by CSI", "credit": credit_text, "license": "Supplied by CSI"})


def from_commons(country, landmark):
    hits = api({"action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {landmark}",
                "gsrnamespace": 6, "gsrlimit": 30, "prop": "imageinfo",
                "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 2000})
    pages = sorted(hits.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = clean(meta.get("LicenseShortName", {}).get("value", ""))
        w, h = ii.get("width", 0), ii.get("height", 0)
        if not OK_LICENSES.match(lic) or ii.get("mime") != "image/jpeg" or w < 1600 or w / max(h, 1) < 1.3:
            continue
        artist = clean(meta.get("Artist", {}).get("value", "")) or "Unknown author"
        img = Image.open(BytesIO(fetch(ii["thumburl"])))
        needs_credit = not re.match(r"^(public domain|pd|cc0)", lic, re.I)
        credit = {
            "source": "Wikimedia Commons",
            "file": p["title"],
            "page": ii.get("descriptionurl", ""),
            "author": artist,
            "license": lic,
            "credit": f"Photo: {artist}, {lic}, via Wikimedia Commons" if needs_credit else f"Photo: {artist} ({lic}), via Wikimedia Commons",
        }
        save(country, img, credit)
        return True
    sys.exit(f"No reusable landscape photo found for '{landmark}'; try another --landmark, or the cover falls back to the map.")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    country = a[0]
    if "--file" in a:
        from_file(country, a[a.index("--file") + 1], a[a.index("--credit") + 1] if "--credit" in a else "")
    else:
        landmark = a[a.index("--landmark") + 1] if "--landmark" in a else DEFAULT_LANDMARKS.get(country)
        if not landmark:
            sys.exit(f"No default landmark for {country}; pass --landmark \"...\"")
        from_commons(country, landmark)
