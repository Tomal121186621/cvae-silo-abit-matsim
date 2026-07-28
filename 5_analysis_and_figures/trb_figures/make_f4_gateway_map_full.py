#!/usr/bin/env python3
"""F4 (corrected): network map with ALL 18 cordon gateways from gateways_2023.csv —
the demand-side set. 15 with external>0 seed through (gateway-gateway IPF) +
inflow/outflow (gateway-interior) non-resident demand; 3 have zero external gap.
Basemap approach reused from code/make_gateway_map_v7.py.
"""
from pathlib import Path
import pandas as pd, geopandas as gpd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
GPKG = ROOT / "network_validation_2023/v7_base/gis/bmr_validation.gpkg"
GW   = ROOT / "network_validation_2023/calibration/gateways_2023.csv"
OUT  = ROOT / "trb_paper/figures"
CRS  = "EPSG:26985"

plt.rcParams.update({"font.family": "serif", "font.size": 12, "savefig.dpi": 300, "figure.dpi": 120})

SHORT = {  # road -> concise label
    "NO NAME": "I-695/I-95 S", "DEEP RUN RD E": "Deep Run Rd", "COLUMBIA PIKE": "US-29",
    "I-95 NE / JFK Mem Hwy (mainline, ramp-only at edge)": "I-95 NE",
    "I-70 W at Mt Airy (interchange ramps only at edge)": "I-70 W",
    "SOUTHERN MD BLVD": "MD-4 S", "RIDGE RD": "MD-27", "ROBERT CRAIN HWY": "MD-3 S",
    "BLUE STAR MEMORIAL HWY": "US-301", "JOHN HANSON HWY": "US-50",
    "LITTLESTOWN PIKE": "MD-97 N", "TANEYTOWN PIKE": "MD-140 NW", "SOLOMONS ISLAND RD": "MD-2 S",
    "MD-295 Balt-Wash Pkwy (mainline ~106k interior, boundary ~90k)": "MD-295 S",
    "RAMP 6 FR MD 4 EB TO MD 980A SB": "MD-4 ramp", "CASTLETON RD": "Castleton Rd",
    "SUPERIOR ST": "Superior St", "I-83 (Harrisburg Expwy)": "I-83 N",
}

g = pd.read_csv(GW)
g["label"] = g["road"].map(SHORT).fillna(g["road"].str.title())
g["seeded"] = g["external"] > 0
# the full resident-trip anchoring set: every AADT station within 2.5 km of the cordon
anch = pd.read_csv(ROOT / "network_validation_2023/calibration/cordon_stations_expanded_anchored.csv")
gminx, gminy, gmaxx, gmaxy = g.cx.min(), g.cy.min(), g.cx.max(), g.cy.max()
mx = (gmaxx - gminx) * 0.14; my = (gmaxy - gminy) * 0.10
minx, maxx, miny, maxy = gminx - mx, gmaxx + mx, gminy - my * 1.6, gmaxy + my * 1.7

cty = gpd.read_file(GPKG, layer="county_boundaries").to_crs(CRS)
net = gpd.read_file(GPKG, layer="network", bbox=(minx, miny, maxx, maxy))
hw = net.highway.astype(str)
FREE = {"motorway", "motorway_link", "trunk", "trunk_link"}
ART = {"primary", "primary_link", "secondary", "secondary_link"}
COLL = {"tertiary", "tertiary_link", "unclassified"}

fig, ax = plt.subplots(figsize=(14.5, 11.5))
cty.plot(ax=ax, facecolor="white", edgecolor="none", zorder=0)
net[~hw.isin(FREE | ART | COLL)].plot(ax=ax, color="#C3C8CE", linewidth=0.28, zorder=1)
net[hw.isin(COLL)].plot(ax=ax, color="#A9B4BF", linewidth=0.42, zorder=2)
net[hw.isin(ART)].plot(ax=ax, color="#7E93A8", linewidth=0.7, zorder=3)
net[hw.isin(FREE)].plot(ax=ax, color="#37546F", linewidth=1.5, zorder=4,
                        capstyle="round", joinstyle="round")
cty.boundary.plot(ax=ax, color="#7A7160", linewidth=1.1, zorder=4)

ax.scatter(anch.x, anch.y, s=26, marker="o", facecolors="#E8A33D", edgecolors="#8a5a00",
           linewidth=0.5, zorder=5, alpha=0.9)
sd, zg = g[g.seeded], g[~g.seeded]
ax.scatter(sd.cx, sd.cy, s=90 + 340 * sd.external / sd.external.max(), marker="*",
           c="#B01B2E", edgecolors="white", linewidth=1.2, zorder=5)
ax.scatter(zg.cx, zg.cy, s=200, marker="*", facecolors="white",
           edgecolors="#B01B2E", linewidth=1.6, zorder=5)

cxm, cym = g.cx.mean(), g.cy.mean()
OVERRIDE = {"I-695/I-95 S": (0.6, -1.5), "MD-4 ramp": (1.5, -0.7), "MD-2 S": (1.4, -1.1),
            "Castleton Rd": (-0.3, 1.6), "Superior St": (1.7, -0.6), "I-95 NE": (1.8, 0.9),
            "MD-140 NW": (-1.5, 0.6), "MD-97 N": (-0.4, 1.5), "Deep Run Rd": (1.5, 0.2),
            "I-70 W": (-1.5, -0.4)}
for _, r in g.iterrows():
    dx, dy = OVERRIDE.get(r["label"], ((1 if r.cx >= cxm else -1) * 1.3, (1 if r.cy >= cym else -1) * 1.0))
    ax.annotate(r["label"], (r.cx, r.cy), xytext=(dx * 55, dy * 55), textcoords="offset points",
                fontsize=10.5, weight="bold", ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.28", fc="white", ec="#B01B2E", lw=0.8, alpha=0.95),
                arrowprops=dict(arrowstyle="-", lw=0.8, color="#8A2432"), zorder=6)

ax.set_xlim(minx, maxx); ax.set_ylim(miny, maxy); ax.set_aspect("equal")
ax.set_title("Study-area cordon gateways and MATSim network — Baltimore Region")
ax.set_xlabel("Easting [m, EPSG:26985]"); ax.set_ylabel("Northing [m]")
handles = [
    Line2D([0], [0], color="#37546F", lw=2.2, label="Freeway / interstate"),
    Line2D([0], [0], color="#7E93A8", lw=1.6, label="Arterial (primary·secondary)"),
    Line2D([0], [0], color="#A9B4BF", lw=1.2, label="Collector (tertiary·unclassified)"),
    Line2D([0], [0], color="#C3C8CE", lw=0.9, label="Local / residential"),
    Line2D([0], [0], color="#7A7160", lw=1.4, label="County boundary"),
    Line2D([0], [0], marker="*", color="none", markerfacecolor="#B01B2E", markeredgecolor="white",
           markersize=19, label=f"Cordon gateway, seeds external demand (n={len(sd)}); size ∝ external veh/day"),
    Line2D([0], [0], marker="*", color="none", markerfacecolor="white", markeredgecolor="#B01B2E",
           markersize=17, label=f"Cordon gateway, zero external gap (n={len(zg)})"),
    Line2D([0], [0], marker="o", color="none", markerfacecolor="#E8A33D", markeredgecolor="#8a5a00",
           markersize=8, label=f"Resident-trip anchor crossing (n={len(anch)}, all AADT stations ≤2.5 km of cordon)"),
]
ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5), framealpha=0.95,
          fontsize=11.5, title="Legend", title_fontsize=12)
fig.savefig(OUT / "F4_network_gateways_map.pdf", bbox_inches="tight")
fig.savefig(OUT / "F4_network_gateways_map.png", bbox_inches="tight")
print("wrote corrected F4 (18 gateways)")
