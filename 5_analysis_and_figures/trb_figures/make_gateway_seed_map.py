#!/usr/bin/env python3
"""TRB figure: cordon gateways with the seeded external background demand — through
(gateway-to-gateway) and inflow/outflow (gateway-to-interior) — sized and labeled with
the daily seeded volume. Gateways with no residual gap (resident demand alone meets or
exceeds the observed crossing count) are shown open."""
from pathlib import Path
import pandas as pd, geopandas as gpd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
GPKG = ROOT / "network_validation_2023/v7_base/gis/bmr_validation.gpkg"
GW = ROOT / "network_validation_2023/calibration/gateways_2023.csv"
OUT = ROOT / "trb_paper/figures"
CRS = "EPSG:26985"

plt.rcParams.update({"font.family": "serif", "font.size": 12, "savefig.dpi": 300, "figure.dpi": 120})

SHORT = {
    "NO NAME": "I-95 SW", "DEEP RUN RD E": "Deep Run Rd", "COLUMBIA PIKE": "US-29",
    "I-95 NE / JFK Mem Hwy (mainline, ramp-only at edge)": "I-95 NE",
    "I-70 W at Mt Airy (interchange ramps only at edge)": "I-70 W",
    "SOUTHERN MD BLVD": "MD-4 S", "RIDGE RD": "MD-27 NW", "ROBERT CRAIN HWY": "MD-3 S",
    "BLUE STAR MEMORIAL HWY": "US-301 S", "JOHN HANSON HWY": "US-50 E",
    "LITTLESTOWN PIKE": "MD-97 N", "TANEYTOWN PIKE": "MD-140 NW", "SOLOMONS ISLAND RD": "MD-2 S",
    "MD-295 Balt-Wash Pkwy (mainline ~106k interior, boundary ~90k)": "MD-295 S",
    "RAMP 6 FR MD 4 EB TO MD 980A SB": "MD-4 ramp", "CASTLETON RD": "Castleton Rd",
    "SUPERIOR ST": "Superior St", "I-83 (Harrisburg Expwy)": "I-83 N",
}

g = pd.read_csv(GW)
g["label"] = g.road.map(SHORT).fillna(g.road.str.title())
g["seeded"] = g.external > 0
mx, my = 24000, 20000
minx, maxx = g.cx.min()-mx, g.cx.max()+mx
miny, maxy = g.cy.min()-my, g.cy.max()+my

cty = gpd.read_file(GPKG, layer="county_boundaries").to_crs(CRS)
net = gpd.read_file(GPKG, layer="network", bbox=(minx, miny, maxx, maxy))
hw = net.highway.astype(str)
FREE = {"motorway", "motorway_link", "trunk", "trunk_link"}
ART = {"primary", "primary_link", "secondary", "secondary_link"}

fig, ax = plt.subplots(figsize=(14.5, 11.5))
COLL = {"tertiary", "tertiary_link", "unclassified"}
cty.plot(ax=ax, facecolor="white", edgecolor="none", zorder=0)
net[~hw.isin(FREE | ART | COLL)].plot(ax=ax, color="#C9CED4", linewidth=0.28, zorder=1)
net[hw.isin(COLL)].plot(ax=ax, color="#AEB8C2", linewidth=0.42, zorder=2)
net[hw.isin(ART)].plot(ax=ax, color="#7E93A8", linewidth=0.7, zorder=2.5)
net[hw.isin(FREE)].plot(ax=ax, color="#37546F", linewidth=1.4, zorder=3,
                        capstyle="round", joinstyle="round")
cty.boundary.plot(ax=ax, color="#7A7160", linewidth=1.0, zorder=4)

ax.scatter(g.cx, g.cy, s=430, marker="*", c="#B01B2E", edgecolors="white",
           linewidth=1.3, zorder=6)

OFF = {  # label push directions (dx, dy) in points
    "I-95 SW": (-1.3, -1.7), "I-95 NE": (1.6, 0.9), "I-83 N": (0.9, -1.4),
    "US-301 S": (1.7, -0.5), "US-50 E": (1.8, 0.4), "MD-295 S": (-1.9, 0.3),
    "MD-2 S": (2.4, -0.6), "MD-27 NW": (-1.6, 0.8), "MD-140 NW": (-1.7, 0.1),
    "MD-97 N": (-1.2, 1.1), "Deep Run Rd": (-1.5, -0.8), "Castleton Rd": (-0.4, 1.3),
    "Superior St": (1.8, -0.3), "I-70 W": (-1.7, -0.5), "US-29": (-2.1, 0.5),
    "MD-3 S": (-1.3, -1.0), "MD-4 S": (1.6, 1.2), "MD-4 ramp": (1.9, -0.9),
}
for _, r in g.iterrows():
    dx, dy = OFF.get(r.label, (1.4, 1.0))
    txt = r.label
    ax.annotate(txt, (r.cx, r.cy), xytext=(dx*62, dy*62), textcoords="offset points",
                fontsize=10.5, weight="bold", ha="center", va="center", color="#111111",
                bbox=dict(boxstyle="round,pad=0.3", fc="white",
                          ec="#B01B2E" if r.seeded else "#999999", lw=0.9, alpha=0.95),
                arrowprops=dict(arrowstyle="-", lw=0.8, color="#8A2432"), zorder=7)

# regional (harbor) crossings — the three tolled water crossings
CROSSINGS = [("Fort McHenry Tunnel (I-95)", 437054, 176417, (-2.5, 0.9)),
             ("Baltimore Harbor Tunnel (I-895)", 436050, 177150, (-3.1, 1.9)),
             ("Francis Scott Key Bridge (I-695)", 439700, 172000, (1.8, -1.2))]
for name, x, y, (dx, dy) in CROSSINGS:
    ax.scatter([x], [y], s=300, marker="o", c="#00695C", edgecolors="white",
               linewidth=1.4, zorder=6)
    ax.annotate("$", (x, y), ha="center", va="center", fontsize=11, weight="bold",
                color="white", zorder=7)
    ax.annotate(f"{name}\n\$3.00 toll (2023)", (x, y), xytext=(dx*62, dy*62),
                textcoords="offset points", fontsize=10, weight="bold",
                ha="center", va="center", color="#00443E",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#00695C", lw=0.9, alpha=0.95),
                arrowprops=dict(arrowstyle="-", lw=0.8, color="#00695C"), zorder=7)
ax.set_xlim(minx, maxx); ax.set_ylim(miny, maxy); ax.set_aspect("equal")
ax.set_title("Cordon gateways for external through and inflow/outflow traffic — Baltimore Region")
ax.set_xlabel("Easting (m, EPSG:26985)"); ax.set_ylabel("Northing (m)")
handles = [
    Line2D([0], [0], color="#37546F", lw=2.0, label="Freeway / interstate"),
    Line2D([0], [0], color="#7E93A8", lw=1.6, label="Arterial"),
    Line2D([0], [0], color="#AEB8C2", lw=1.2, label="Collector"),
    Line2D([0], [0], color="#C9CED4", lw=0.9, label="Local / residential"),
    Line2D([0], [0], color="#7A7160", lw=1.4, label="County boundary"),
    Line2D([0], [0], marker="*", color="none", markerfacecolor="#B01B2E", markeredgecolor="white",
           markersize=22, label=f"Cordon gateway for external traffic\n(through + inflow/outflow), n={len(g)}"),
    Line2D([0], [0], marker="o", color="none", markerfacecolor="#00695C", markeredgecolor="white",
           markersize=14, label="Harbor crossing with baseline toll\n(\$3.00 both directions, MDTA 2023)"),
]
ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5),
          framealpha=0.95, fontsize=11.5, title="Legend", title_fontsize=12)
fig.savefig(OUT / "F5_gateway_seed_map.pdf", bbox_inches="tight")
fig.savefig(OUT / "F5_gateway_seed_map.png", bbox_inches="tight")
print("wrote F5_gateway_seed_map (plan map, no volumes)")
