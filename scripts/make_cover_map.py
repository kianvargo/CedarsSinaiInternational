#!/usr/bin/env python3
"""Render a cover map: white world on Cedars red, with one country highlighted.

Usage: python3 make_cover_map.py <Country name> <output.png>
Shapes: Natural Earth 1:110m admin-0 countries (public domain), assets/ne_110m_countries.geojson.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

GEOJSON = Path(__file__).resolve().parent.parent / "assets" / "ne_110m_countries.geojson"
RED = "#D91F2C"
HIGHLIGHT = "#6E0E14"


def rings(geom):
    if geom["type"] == "Polygon":
        yield geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield poly[0]


def matches(props, name):
    name = name.lower()
    return any(str(props.get(k, "")).lower() == name for k in ("NAME", "NAME_LONG", "ADMIN", "NAME_EN", "SOVEREIGNT"))


def main(country, out_path):
    features = json.loads(GEOJSON.read_text())["features"]
    target = [f for f in features if matches(f["properties"], country)]
    if not target:
        sys.exit(f"Country '{country}' not found in Natural Earth names")

    fig, ax = plt.subplots(figsize=(12, 5.4), dpi=200)
    fig.patch.set_facecolor(RED)
    ax.set_facecolor(RED)
    for f in features:
        is_target = f in target
        for ring in rings(f["geometry"]):
            ax.add_patch(Polygon(ring, closed=True,
                                 facecolor=HIGHLIGHT if is_target else "white",
                                 edgecolor=RED if not is_target else "white",
                                 linewidth=0.3 if not is_target else 0.8,
                                 zorder=3 if is_target else 2))
    ax.set_xlim(-170, 190)
    ax.set_ylim(-58, 84)
    ax.set_aspect("equal")
    ax.axis("off")
    plt.subplots_adjust(0, 0, 1, 1)
    fig.savefig(out_path, facecolor=RED)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 make_cover_map.py <Country> <output.png>")
    main(sys.argv[1], sys.argv[2])
