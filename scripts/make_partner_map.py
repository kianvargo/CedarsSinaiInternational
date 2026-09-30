#!/usr/bin/env python3
"""
One-page map of foreign health-system partnerships in a country, from the
verified tracker (data/partnerships.json) and the partner-city file
(data/<country>_partner_locations.json).

Usage: python3 make_partner_map.py India output/India_partnerships_map.png

Red circles: active partnerships per city (area proportional to count).
Dark squares: the largest metros, shown whether or not they have partnerships.
Boundaries: Natural Earth 1:50m (public domain); not an official depiction.
"""
import json
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
    return 40 + 48 * n


def rings(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for poly in polys:
        yield poly[0]


def main(country, out):
    cfg = COUNTRIES[country]
    tracker = json.loads((ROOT / "data" / "partnerships.json").read_text())["relationships"]
    locs = json.loads((ROOT / "data" / f"{country.lower()}_partner_locations.json").read_text())["locations"]
    rows = [r for r in tracker if r["country"] == country]
    active = Counter(c for r in rows if r["status"] == "Active" for c in locs[r["id"]]["cities"])
    unclear = Counter(c for r in rows if r["status"] == "Unclear" for c in locs[r["id"]]["cities"])

    features = json.loads((ROOT / "assets" / "ne_50m_countries.geojson").read_text())["features"]
    x0, x1, y0, y1 = cfg["bounds"]
    fig, ax = plt.subplots(figsize=(7.0, 7.6), dpi=220)
    for f in features:
        is_c = f["properties"].get("ADMIN") == country or f["properties"].get("NAME") == country
        for ring in rings(f["geometry"]):
            ax.add_patch(Polygon(ring, closed=True, facecolor="#F4F1EC" if is_c else "#FAFAFA",
                                 edgecolor="#8C8A85" if is_c else "#DAD8D2", linewidth=0.8 if is_c else 0.4,
                                 zorder=2 if is_c else 1))

    # Metros first (dark squares), then partnership circles on top
    for name in cfg["metros"]:
        (lon, lat), _ = cfg["cities"][name]
        ax.scatter([lon], [lat], marker="s", s=22, color=INK, zorder=4)
    for name, n in active.items():
        (lon, lat), _ = cfg["cities"][name]
        ax.scatter([lon], [lat], s=size(n), color=RED, alpha=0.9, edgecolor="white", linewidth=1.2, zorder=5)
        ax.text(lon, lat, str(n), ha="center", va="center", fontsize=8 if n < 10 else 7, color="white",
                fontweight="bold", zorder=6)
    for name, n in unclear.items():
        if name not in active:
            (lon, lat), _ = cfg["cities"][name]
            ax.scatter([lon], [lat], s=90, facecolor="white", edgecolor=INK_2, linewidth=1.2, zorder=5)

    labelled = set(cfg["metros"]) | set(active) | set(unclear)
    for name in labelled:
        (lon, lat), (dx, dy) = cfg["cities"][name]
        radius = (size(active[name]) ** 0.5) / 2 if active.get(name) else 5
        if dx != 0:
            dx = (1 if dx > 0 else -1) * (radius + 4 + abs(dx) * 0.2)
        parts = []
        if active.get(name):
            parts.append(f"{active[name]} active")
        if unclear.get(name):
            parts.append(f"{unclear[name]} unclear")
        is_metro = name in cfg["metros"]
        ax.annotate(name, (lon, lat), xytext=(dx, dy), textcoords="offset points",
                    ha="center" if dx == 0 else ("left" if dx > 0 else "right"), va="center", fontsize=9 if is_metro else 8,
                    fontweight="bold" if is_metro else "normal", color=INK, zorder=7)
        if parts:
            ax.annotate(", ".join(parts), (lon, lat), xytext=(dx, dy - 10), textcoords="offset points",
                        ha="center" if dx == 0 else ("left" if dx > 0 else "right"), va="center", fontsize=7, color=INK_2, zorder=7)
        elif is_metro:
            ax.annotate("none found", (lon, lat), xytext=(dx, dy - 10), textcoords="offset points",
                        ha="left" if dx >= 0 else "right", va="center", fontsize=7, color=INK_2, zorder=7)

    handles = [
        Line2D([], [], marker="o", linestyle="", markersize=11, markerfacecolor=RED, markeredgecolor="white",
               label="Active partnerships (number in circle)"),
        Line2D([], [], marker="o", linestyle="", markersize=8, markerfacecolor="white", markeredgecolor=INK_2,
               label="Unclear status only"),
        Line2D([], [], marker="s", linestyle="", markersize=5, color=INK, label="Major metro"),
    ]
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=8, labelcolor=INK, borderaxespad=0.2)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect(1.0 / 0.93)  # rough latitude correction for India's mid-latitudes
    ax.axis("off")
    plt.subplots_adjust(0, 0, 1, 1)
    fig.savefig(out, facecolor="white")
    print(f"Wrote {out}: active {dict(active)}, unclear {dict(unclear)}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 make_partner_map.py <Country> <out.png>")
    main(sys.argv[1], sys.argv[2])
