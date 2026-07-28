#!/usr/bin/env python3
"""figS1 (screenline map) restyled to match the F5 gateway map: same basemap palette,
serif labels with leader boxes, right-side legend, EPSG axes. Screenlines + captured
count stations + Interstate/major-road labels."""
from pathlib import Path
import pandas as pd, geopandas as gpd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
GPKG = ROOT / "network_validation_2023/v7_base/gis/bmr_validation.gpkg"
ST = ROOT / "trb_paper/figures/screenlines/screenline_stations.csv"
OUT = ROOT / "trb_paper/figures/screenlines"
CRS = "EPSG:26985"

plt.rcParams.update({"font.family": "serif", "font.size": 12, "savefig.dpi": 300, "figure.dpi": 120})

SL = {
    "A  Patapsco Harbor": ((434500, 177500), (444500, 171500)),
    "B  North line": ((412000, 197500), (447000, 197500)),
    "C  West line": ((414500, 168000), (414500, 200000)),
    "D  South line": ((405000, 158500), (450000, 158500)),
    "E  East line": ((448500, 170000), (448500, 206000)),
}
SLCOL = {"A  Patapsco Harbor": "#D55E00", "B  North line": "#0072B2", "C  West line": "#009E73",
         "D  South line": "#CC79A7", "E  East line": "#E69F00"}
LBL_OFF = {"A  Patapsco Harbor": (446000, 170300), "B  North line": (448200, 197500),
           "C  West line": (414500, 201500), "D  South line": (451200, 158500),
           "E  East line": (448500, 207500)}

minx, maxx, miny, maxy = 405000, 458000, 149000, 213000
cty = gpd.read_file(GPKG, layer="county_boundaries").to_crs(CRS)
net = gpd.read_file(GPKG, layer="network", bbox=(minx, miny, maxx, maxy))
hw = net.highway.astype(str)
FREE = {"motorway", "motorway_link", "trunk", "trunk_link"}
ART = {"primary", "primary_link", "secondary", "secondary_link"}
COLL = {"tertiary", "tertiary_link", "unclassified"}

fig, ax = plt.subplots(figsize=(12.5, 13.5))
cty.plot(ax=ax, facecolor="white", edgecolor="none", zorder=0)
net[~hw.isin(FREE | ART | COLL)].plot(ax=ax, color="#C3C8CE", linewidth=0.30, zorder=1)
net[hw.isin(COLL)].plot(ax=ax, color="#A9B4BF", linewidth=0.45, zorder=2)
net[hw.isin(ART)].plot(ax=ax, color="#7E93A8", linewidth=0.75, zorder=2.5)
net[hw.isin(FREE)].plot(ax=ax, color="#37546F", linewidth=1.45, zorder=3,
                        capstyle="round", joinstyle="round")
cty.boundary.plot(ax=ax, color="#7A7160", linewidth=1.0, zorder=4)

st = pd.read_csv(ST)
qa = pd.read_csv(ROOT / "network_validation_2023/transitfix/aadt/aadt_validation_2023_qa_v2.csv")
spos = dict(zip(qa.LOCATION_ID, zip(qa.lon, qa.lat)))   # true station coords (EPSG:26985)
for name, ((x1, y1), (x2, y2)) in SL.items():
    c = SLCOL[name]
    ax.plot([x1, x2], [y1, y2], color=c, lw=3.0, zorder=5, solid_capstyle="round")
    lx, ly = LBL_OFF[name]
    ax.annotate(name.split("  ")[1] if "Patapsco" not in name else "Patapsco Harbor",
                (lx, ly), fontsize=12, weight="bold", color=c, ha="left", va="center",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=c, lw=1.0, alpha=0.95), zorder=7)
    sub = st[st.screenline == name]
    if len(sub):
        ax.scatter(sub.x, sub.y, s=30, marker="s", color=c, edgecolors="white", linewidth=0.6, zorder=6)
        for r in sub.itertuples():   # paired AADT station + connector to its capture point
            sp = spos.get(r.station)
            if sp:
                ax.plot([r.x, sp[0]], [r.y, sp[1]], color=c, lw=0.6, alpha=0.55, zorder=5)
                ax.scatter([sp[0]], [sp[1]], s=34, color=c, edgecolors="white",
                           linewidth=0.8, zorder=6)
# Harbor line is measured at the three MDTA crossings (toll transaction counts), not AADT stations
HX = [(437054, 176417), (436050, 177150), (439700, 172000)]
ax.scatter([h[0] for h in HX], [h[1] for h in HX], s=46, marker="s",
           color=SLCOL["A  Patapsco Harbor"], edgecolors="white", linewidth=0.8, zorder=6)

# Interstate / major-road labels (same set as before, F5 styling)
ROADLBL = [
    ("I-95", 413800, 161000, 38), ("I-95", 445800, 192800, 40),
    ("I-695", 425600, 185300, 85), ("I-695", 444300, 175800, -60),
    ("I-83", 430700, 203800, 80), ("I-70", 411800, 182000, 0),
    ("I-795", 417600, 197400, -40), ("I-895", 434300, 172300, 30),
    ("I-97", 433900, 153800, 78), ("MD-295", 422600, 168300, 42),
    ("MD-100", 421500, 161300, 0),
]
for name, x, y, rot in ROADLBL:
    ax.text(x, y, name, fontsize=9.5, fontweight="bold", color="#333333",
            ha="center", va="center", rotation=rot, rotation_mode="anchor", zorder=7,
            bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="#999999", lw=0.5, alpha=0.88))

ax.set_xlim(minx, maxx); ax.set_ylim(miny, maxy); ax.set_aspect("equal")
ax.set_title("Screenlines, crossing capture points, and paired AADT stations — Baltimore Region")
ax.set_xlabel("Easting (m, EPSG:26985)"); ax.set_ylabel("Northing (m)")
handles = [Line2D([0], [0], color="#37546F", lw=2.2, label="Freeway / interstate"),
           Line2D([0], [0], color="#7E93A8", lw=1.6, label="Arterial"),
           Line2D([0], [0], color="#A9B4BF", lw=1.2, label="Collector (tertiary·unclassified)"),
           Line2D([0], [0], color="#C3C8CE", lw=0.9, label="Local / residential"),
           Line2D([0], [0], color="#7A7160", lw=1.4, label="County boundary")]
handles += [Line2D([0], [0], color=SLCOL[n], lw=3,
                   label=f"{n.split('  ')[1] if 'Patapsco' not in n else 'Patapsco Harbor'} screenline")
            for n in SL]
handles += [Line2D([0], [0], marker="s", color="none", markerfacecolor="#666666",
                   markeredgecolor="white", markersize=9, label="Crossing capture link on line\n(MDTA crossings on Harbor line)"),
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#666666",
                   markeredgecolor="white", markersize=9, label="Paired AADT count station\n(connector = road-name pairing)")]
ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.02, 0.5),
          framealpha=0.95, fontsize=11.5, title="Legend", title_fontsize=12)
fig.savefig(OUT / "figS1_screenline_map.pdf", bbox_inches="tight")
fig.savefig(OUT / "figS1_screenline_map.png", bbox_inches="tight")
print("wrote uniform figS1_screenline_map")
