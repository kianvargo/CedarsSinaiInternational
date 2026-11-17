#!/usr/bin/env python3
"""
One-page map of foreign health-system partnerships in a country, from the
verified tracker (data/partnerships.json) and the partner-city file
(data/<country>_partner_locations.json).

Usage: python3 make_partner_map.py India output/India_partnerships_map.png

Map settings (bounds, big metros, city coordinates and label offsets) come from COUNTRIES
below or, for any other country, from optional "bounds", "metros" and "cities" keys in the
partner-location file, with cities written as {"Cairo": [[31.24, 30.04], [10, 6]]}.

Optional keys in the partner-location file for crowded countries (Japan): "compact": true (drop the
"N active" sub-labels), "merged": {name: {"cities": [...], "at": [lon, lat], "offset": [dx, dy]}} (several
nearby cities drawn as one bubble), "clusters": the same plus "inset": {"bounds": [lon0, lon1, lat0, lat1],
"anchor": [x, y], "width": fraction of figure width, "labels": {city: [dx, dy]}} (one bubble on the main map and
a zoomed inset with the individual cities), and "legend": {"loc": "lower right"}.

Red circles: active partnerships per city (area proportional to count). Only active
partnerships are mapped; unclear and ended ones stay in the tracker.
Dark squares: the largest metros, shown whether or not they have partnerships.
Boundaries: Natural Earth 1:50m (public domain); not an official depiction.
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon

ROOT = Path(__file__).resolve().parent.parent
RED = "#D91F2C"
INK = "#0b0b0b"
INK_2 = "#52514e"

COUNTRIES = {
    "India": {
        "bounds": (67.5, 98.5, 6.0, 36.5),
        "metros": ["Delhi NCR", "Mumbai", "Kolkata", "Bengaluru", "Chennai", "Hyderabad", "Ahmedabad", "Pune"],
        # (lon, lat), label offset in points
        "cities": {
            "Delhi NCR": ((77.21, 28.61), (10, 6)),
            "Mumbai": ((72.88, 19.08), (-14, -2)),
            "Kolkata": ((88.36, 22.57), (10, 0)),
            "Bengaluru": ((77.59, 12.97), (-14, -6)),
            "Chennai": ((80.27, 13.08), (12, 0)),
            "Hyderabad": ((78.49, 17.39), (12, 2)),
            "Ahmedabad": ((72.57, 23.02), (-14, 4)),
            "Pune": ((73.86, 18.52), (8, -6)),
            "Belagavi": ((74.50, 15.85), (-12, -4)),
            "Loni": ((74.45, 19.58), (10, 6)),
            "Madurai": ((78.12, 9.93), (10, -4)),
            "Jammu": ((74.86, 32.73), (10, 4)),
            "Dehradun": ((78.03, 30.32), (10, 4)),
            "Vellore": ((79.13, 12.92), (0, -14)),
        },
    }
}


def size(n):
    return min(170 + 36 * n, 1000)  # smallest circle still fits its number; very large counts are capped


def rings(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for poly in polys:
        yield poly[0]


def main(country, out):
    tracker = json.loads((ROOT / "data" / "partnerships.json").read_text())["relationships"]
    locfile = json.loads((ROOT / "data" / f"{country.lower().replace(' ', '_')}_partner_locations.json").read_text())
    locs = locfile["locations"]
    cfg = {**COUNTRIES.get(country, {}), **{k: locfile[k] for k in ("bounds", "metros") if k in locfile}}
    cfg["cities"] = {**cfg.get("cities", {}), **{k: (tuple(v[0]), tuple(v[1])) for k, v in locfile.get("cities", {}).items()}}
    rows = [r for r in tracker if r["country"] == country]
    active = Counter(c for r in rows if r["status"] == "Active" for c in locs[r["id"]]["cities"])

    features = json.loads((ROOT / "assets" / "ne_50m_countries.geojson").read_text())["features"]
    x0, x1, y0, y1 = cfg["bounds"]
    aspect = 1.0 / math.cos(math.radians((y0 + y1) / 2))
    ratio = (y1 - y0) * aspect / (x1 - x0)
    fig, ax = plt.subplots(figsize=(7.0, 7.0 * ratio), dpi=220)
    for f in features:
        is_c = f["properties"].get("ADMIN") == country or f["properties"].get("NAME") == country
        for ring in rings(f["geometry"]):
            ax.add_patch(Polygon(ring, closed=True, facecolor="#F4F1EC" if is_c else "#FAFAFA",
                                 edgecolor="#8C8A85" if is_c else "#DAD8D2", linewidth=0.8 if is_c else 0.4,
                                 zorder=2 if is_c else 1))

    compact = locfile.get("compact", False)
    groups = {**locfile.get("merged", {}), **locfile.get("clusters", {})}
    grouped = {c for g in groups.values() for c in g["cities"]}
    # name -> (lon, lat, count, label offset, bold)
    bubbles = {}
    for name, n in active.items():
        if name not in grouped:
            (lon, lat), off = cfg["cities"][name]
            bubbles[name] = (lon, lat, n, off, name in cfg["metros"])
    for gname, g in groups.items():
        n = sum(active.get(c, 0) for c in g["cities"])
        if n:
            bubbles[gname] = (g["at"][0], g["at"][1], n, tuple(g["offset"]), True)

    # Metros first (dark squares), then partnership circles on top
    for name in cfg["metros"]:
        if name in grouped:
            continue
        (lon, lat), _ = cfg["cities"][name]
        ax.scatter([lon], [lat], marker="s", s=22, color=INK, zorder=4)
    for name, (lon, lat, n, _, _) in bubbles.items():
        ax.scatter([lon], [lat], s=size(n), color=RED, alpha=0.9, edgecolor="white", linewidth=1.2, zorder=5)
        ax.text(lon, lat, str(n), ha="center", va="center", fontsize=7.5, color="white",
                fontweight="bold", zorder=6)

    def put_label(ax_, name, lon, lat, off, radius, bold, sub=None, fs=8):
        dx, dy = off
        if dx != 0:
            dx = (1 if dx > 0 else -1) * (radius + 4 + abs(dx) * 0.2)
        ha = "center" if dx == 0 else ("left" if dx > 0 else "right")
        ax_.annotate(name, (lon, lat), xytext=(dx, dy), textcoords="offset points", ha=ha, va="center",
                     fontsize=fs + 1 if bold else fs, fontweight="bold" if bold else "normal", color=INK, zorder=7)
        if sub:
            ax_.annotate(sub, (lon, lat), xytext=(dx, dy - 10), textcoords="offset points", ha=ha, va="center",
                         fontsize=7, color=INK_2, zorder=7)

    for name, (lon, lat, n, off, bold) in bubbles.items():
        put_label(ax, name, lon, lat, off, (size(n) ** 0.5) / 2, bold, None if compact else f"{n} active")
    for name in cfg["metros"]:
        if name in grouped or name in bubbles:
            continue
        (lon, lat), off = cfg["cities"][name]
        put_label(ax, name, lon, lat, off, 5, True, None if compact else "none found")

    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect(aspect)  # latitude correction
    ax.axis("off")

    # Zoomed insets for crowded areas
    for gname, g in locfile.get("clusters", {}).items():
        spec = g.get("inset")
        n_total = bubbles.get(gname, (0, 0, 0))[2]
        if not spec or not n_total:
            continue
        ix0, ix1, iy0, iy1 = spec["bounds"]
        iasp = 1.0 / math.cos(math.radians((iy0 + iy1) / 2))
        fw, fh = fig.get_size_inches()
        w = spec["width"]
        h = w * fw * (iy1 - iy0) * iasp / (ix1 - ix0) / fh
        ax2 = fig.add_axes([spec["anchor"][0], spec["anchor"][1], w, h])
        for f in features:
            if f["properties"].get("ADMIN") == country or f["properties"].get("NAME") == country:
                for ring in rings(f["geometry"]):
                    ax2.add_patch(Polygon(ring, closed=True, facecolor="#F4F1EC", edgecolor="#8C8A85", linewidth=0.8))
        ax2.set_xlim(ix0, ix1)
        ax2.set_ylim(iy0, iy1)
        ax2.set_aspect(iasp)
        ax2.set_xticks([])
        ax2.set_yticks([])
        for sp in ax2.spines.values():
            sp.set_edgecolor(RED)
            sp.set_linewidth(1.2)
        small = lambda n: 150 + 9 * n
        for city in g["cities"]:
            n = active.get(city, 0)
            if not n:
                continue
            (lon, lat), _ = cfg["cities"][city]
            ax2.scatter([lon], [lat], s=small(n), color=RED, alpha=0.9, edgecolor="white", linewidth=1.0, zorder=5)
            ax2.text(lon, lat, str(n), ha="center", va="center", fontsize=6.5, color="white", fontweight="bold", zorder=6)
            put_label(ax2, city, lon, lat, tuple(spec["labels"].get(city, (10, 0))), (small(n) ** 0.5) / 2,
                      city in cfg["metros"], None, fs=7.5)
        ax2.set_title(f"{gname}: {n_total} active", fontsize=8, fontweight="bold", color=INK, pad=3)
        # outline on the main map and connectors to the inset
        from matplotlib.patches import ConnectionPatch, Rectangle
        ax.add_patch(Rectangle((ix0, iy0), ix1 - ix0, iy1 - iy0, fill=False, edgecolor=RED, linewidth=1.0, zorder=8))
        bx, by = g["at"]
        ax.plot([ix1, bx], [(iy0 + iy1) / 2, by], color=RED, linewidth=0.8, linestyle=(0, (3, 2)), zorder=3)
        for (cx, cy), (ux, uy) in (((ix0, iy0), (0, 1)), ((ix1, iy0), (1, 1))):
            fig.add_artist(ConnectionPatch((cx, cy), (ux, uy), coordsA=ax.transData, coordsB=ax2.transAxes,
                                           axesA=ax, axesB=ax2, color=RED, linewidth=0.8, linestyle=(0, (3, 2))))

    handles = [
        Line2D([], [], marker="o", linestyle="", markersize=11, markerfacecolor=RED, markeredgecolor="white",
               label="Active partnerships (number in circle)"),
        Line2D([], [], marker="s", linestyle="", markersize=5, color=INK, label="Major metro"),
    ]
    ax.legend(handles=handles, loc=locfile.get("legend", {}).get("loc", "lower left"), frameon=False, fontsize=8,
              labelcolor=INK, borderaxespad=0.2)
    plt.subplots_adjust(0, 0, 1, 1)
    fig.savefig(out, facecolor="white")
    print(f"Wrote {out}: active {dict(active)}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 make_partner_map.py <Country> <out.png>")
    main(sys.argv[1], sys.argv[2])
