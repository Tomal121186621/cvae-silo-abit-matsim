#!/usr/bin/env python3
"""Regenerate the screenline map for the paper, WITHOUT the Patapsco Harbor line.

The harbor screenline has no AADT count stations in screenline_stations.csv (its
counts come from the tolled harbor crossings, validated separately in the count
figures), so it is dropped here to keep the map consistent: every screenline shown
carries its captured AADT stations. Output overwrites figures/matsim/screenline_map_orig.
"""
from pathlib import Path
import pandas as pd, geopandas as gpd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

MAT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
GPKG = MAT / "network_validation_2023/v7_base/gis/bmr_validation.gpkg"
ST = MAT / "trb_paper/figures/screenlines/screenline_stations.csv"
OUT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Paper Figures Final/figures/matsim")
CRS = "EPSG:26985"

plt.rcParams.update({"font.family": "serif", "font.size": 12, "savefig.dpi": 300, "figure.dpi": 120})

# 4 directional screenlines only (harbor dropped)
SL = {
    "B  North line": ((412000, 197500), (447000, 197500)),
    "C  West line": ((414500, 168000), (414500, 200000)),
    "D  South line": ((405000, 158500), (450000, 158500)),
    "E  East line": ((448500, 170000), (448500, 206000)),
}
SLCOL = {"B  North line": "#0072B2", "C  West line": "#009E73",
         "D  South line": "#CC79A7", "E  East line": "#E69F00"}
LBL_OFF = {"B  North line": (448200, 197500), "C  West line": (414500, 201500),
           "D  South line": (451200, 158500), "E  East line": (448500, 207500)}

minx, maxx, miny, maxy = 405000, 458000, 149000, 213000
cty = gpd.read_file(GPKG, layer="county_boundaries").to_crs(CRS)
net = gpd.read_file(GPKG, layer="network", bbox=(minx, miny, maxx, maxy))
hw = net.highway.astype(str)
FREE = {"motorway", "motorway_link", "trunk", "trunk_link"}
ART = {"primary", "primary_link", "secondary", "secondary_link"}

fig, ax = plt.subplots(figsize=(12.5, 13.5))
cty.plot(ax=ax, facecolor="#F5F2EA", edgecolor="none", zorder=0)
net[~hw.isin(FREE | ART)].plot(ax=ax, color="#D5D8DC", linewidth=0.18, zorder=1)
net[hw.isin(ART)].plot(ax=ax, color="#9DABB9", linewidth=0.45, zorder=2)
net[hw.isin(FREE)].plot(ax=ax, color="#37546F", linewidth=1.15, zorder=3)
cty.boundary.plot(ax=ax, color="#7A7160", linewidth=1.0, zorder=4)

st = pd.read_csv(ST)
for name, ((x1, y1), (x2, y2)) in SL.items():
    c = SLCOL[name]
    ax.plot([x1, x2], [y1, y2], color=c, lw=3.0, zorder=5, solid_capstyle="round")
    lx, ly = LBL_OFF[name]
    ax.annotate(name.split("  ")[1], (lx, ly), fontsize=12, weight="bold", color=c,
                ha="left", va="center",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=c, lw=1.0, alpha=0.95), zorder=7)
    sub = st[st.screenline == name]
    n_st = len(sub)
    if n_st:
        ax.scatter(sub.x, sub.y, s=26, color=c, edgecolors="white", linewidth=0.6, zorder=6)
    print(f"{name}: {n_st} captured stations")

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
ax.set_title("Screenlines and captured AADT count stations — Baltimore Region")
ax.set_xlabel("Easting (m, EPSG:26985)"); ax.set_ylabel("Northing (m)")
handles = [Line2D([0], [0], color="#37546F", lw=2.0, label="Freeway / interstate"),
           Line2D([0], [0], color="#9DABB9", lw=1.4, label="Arterial"),
           Line2D([0], [0], color="#7A7160", lw=1.4, label="County boundary")]
handles += [Line2D([0], [0], color=SLCOL[n], lw=3, label=f"{n.split('  ')[1]} screenline") for n in SL]
handles += [Line2D([0], [0], marker="o", color="none", markerfacecolor="#666666",
                   markeredgecolor="white", markersize=9, label="Captured count station")]
ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.02, 0.5),
          framealpha=0.95, fontsize=11.5, title="Legend", title_fontsize=12)
fig.savefig(OUT / "screenline_map_orig.png", bbox_inches="tight")
fig.savefig(OUT / "screenline_map_orig.pdf", bbox_inches="tight")
print("wrote screenline_map_orig (4 directional screenlines, harbor dropped)")
