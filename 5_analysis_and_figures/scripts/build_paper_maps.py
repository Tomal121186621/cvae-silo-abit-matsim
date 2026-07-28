#!/usr/bin/env python3
"""Vector, paper-style MATSim map exhibits with the full road hierarchy.

  map_gateways.pdf     18 cordon gateways (labeled) + tolled harbor crossings
  map_screenlines.pdf  the five validation screenlines (labeled) + count stations

Roads are drawn as a four-tier hierarchy (freeway, arterial, collector, local)
from the OSM highway tag; major interstate/US corridors are labeled. Dense road
geometry is rasterized at 400 dpi while all text/markers stay vector, keeping the
PDF small and print-sharp. Geometry: bmr_validation.gpkg, gateways_2023.csv,
screenline_stations.csv. CRS EPSG:26985.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_style as ps
ps.apply()
import matplotlib.pyplot as plt
plt.rcParams["savefig.dpi"] = 300
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

MAT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
GPKG = MAT / "network_validation_2023/v7_base/gis/bmr_validation.gpkg"
GW = MAT / "network_validation_2023/calibration/gateways_2023.csv"
SL = MAT / "trb_paper/figures/screenlines/screenline_stations.csv"
OUT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"
           "/Paper Figures Final/figures/matsim")
OUT.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:26985"

STUDY = ["Baltimore City, MD", "Baltimore County, MD", "Anne Arundel County, MD",
         "Howard County, MD", "Harford County, MD", "Carroll County, MD"]

LAND = "#FFFFFF"
LAND_EDGE = "#CFC8B6"
STUDY_FILL = "#E7F1FA"
CTY_LINE = "#C8C1B0"

# road hierarchy (OSM highway tag -> tier)
FREE = {"motorway", "motorway_link", "trunk", "trunk_link"}
ART = {"primary", "primary_link", "secondary", "secondary_link"}
COLL = {"tertiary", "tertiary_link", "unclassified"}
C_FREE, C_ART, C_COLL, C_LOCAL = "#2C4A63", "#7E93A8", "#AEB8C2", "#CDD2D8"
HARBOR = "#0F7B6C"

CROSSINGS = [(437054, 176417), (436050, 177150), (439700, 172000)]

# major interstate / US-route corridor labels (name, x, y, rotation deg)
ROADLBL = [
    ("I-95", 413800, 161000, 38), ("I-95", 445800, 192800, 40),
    ("I-695", 425600, 185300, 85), ("I-695", 444300, 175800, -60),
    ("I-83", 430700, 203800, 80), ("I-70", 402000, 187900, 0),
    ("I-795", 417600, 197400, -40), ("I-895", 434300, 172300, 30),
    ("I-97", 433900, 153800, 78), ("MD-295", 422600, 168300, 42),
    ("US-50", 452500, 148700, 0), ("US-1", 407500, 171500, 55),
]

SL_COLOR = {"A": "#D55E00", "B": "#0072B2", "C": "#009E73", "D": "#CC79A7", "E": "#E69F00"}
SL_LABEL = {"A": "Patapsco Harbor", "B": "North line", "C": "West line",
            "D": "South line", "E": "East line"}


def draw_roads(ax, net, tiers=True):
    hw = net.highway.astype(str)
    if tiers:
        net[~hw.isin(FREE | ART | COLL)].plot(ax=ax, color=C_LOCAL, linewidth=0.18,
                                              zorder=1, rasterized=True)
        net[hw.isin(COLL)].plot(ax=ax, color=C_COLL, linewidth=0.32, zorder=2, rasterized=True)
        net[hw.isin(ART)].plot(ax=ax, color=C_ART, linewidth=0.62, zorder=3, rasterized=True)
    net[hw.isin(FREE)].plot(ax=ax, color=C_FREE, linewidth=1.15, zorder=4,
                            capstyle="round", rasterized=True)


def basemap(ax, cty, study, net, bbox, tiers=True):
    cty.plot(ax=ax, color=LAND, edgecolor="none", zorder=0, rasterized=True)
    study.plot(ax=ax, color=STUDY_FILL, edgecolor="none", zorder=0.5, rasterized=True)
    draw_roads(ax, net, tiers)
    cty.boundary.plot(ax=ax, color=CTY_LINE, linewidth=0.5, zorder=4.5, rasterized=True)
    study.boundary.plot(ax=ax, color="#5B8FB4", linewidth=0.9, zorder=4.6, rasterized=True)
    ax.set_xlim(bbox[0], bbox[2]); ax.set_ylim(bbox[1], bbox[3])
    ax.set_aspect("equal"); ax.set_axis_off()


def road_labels(ax, bbox):
    for name, x, y, rot in ROADLBL:
        if bbox[0] < x < bbox[2] and bbox[1] < y < bbox[3]:
            ax.text(x, y, name, fontsize=6.6, fontweight="bold", color="#33414d",
                    ha="center", va="center", rotation=rot, rotation_mode="anchor", zorder=7,
                    bbox=dict(boxstyle="round,pad=0.14", fc="white", ec="#B9B2A0",
                              lw=0.4, alpha=0.85))


def decorate(ax, bbox, bar_m, bar_label, arrow="tr"):
    W, H = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = bbox[0] + 0.05 * W; y = bbox[1] + 0.05 * H
    ax.plot([x, x + bar_m], [y, y], color="black", lw=2.0, solid_capstyle="butt", zorder=9)
    ax.text(x + bar_m / 2, y + 0.014 * H, bar_label, ha="center", va="bottom",
            fontsize=8.5, zorder=9)
    if arrow == "bl":
        nx, ny = x + bar_m / 2, y + 0.055 * H
    else:
        nx, ny = bbox[2] - 0.055 * W, bbox[3] - 0.17 * H
    ax.annotate("N", xy=(nx, ny + 0.085 * H), xytext=(nx, ny), ha="center", va="bottom",
                fontsize=11, fontweight="bold", zorder=9,
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1.1))


def load_base():
    cty = gpd.read_file(GPKG, layer="county_boundaries").to_crs(CRS)
    return cty, cty[cty.JUR_NAME.isin(STUDY)].copy()


GW_SHORT = {
    "NO NAME": "I-95 SW", "DEEP RUN RD E": "Deep Run Rd", "COLUMBIA PIKE": "US-29",
    "I-95 NE / JFK Mem Hwy (mainline, ramp-only at edge)": "I-95 NE",
    "I-70 W at Mt Airy (interchange ramps only at edge)": "I-70 W",
    "SOUTHERN MD BLVD": "MD-4 S", "RIDGE RD": "MD-27 NW", "ROBERT CRAIN HWY": "MD-3 S",
    "BLUE STAR MEMORIAL HWY": "US-301 S", "JOHN HANSON HWY": "US-50 E",
    "LITTLESTOWN PIKE": "MD-97 N", "TANEYTOWN PIKE": "MD-140 NW", "SOLOMONS ISLAND RD": "MD-2 S",
    "MD-295 Balt-Wash Pkwy (mainline ~106k interior, boundary ~90k)": "MD-295 S",
    "RAMP 6 FR MD 4 EB TO MD 980A SB": "MD-4 (ramp)", "CASTLETON RD": "Castleton Rd",
    "SUPERIOR ST": "Superior St", "I-83 (Harrisburg Expwy)": "I-83 N",
}
GW_OFF = {
    "I-95 SW": (-1.4, -1.2), "I-95 NE": (1.5, 0.7), "I-83 N": (0.2, 1.4),
    "US-301 S": (1.35, -0.35), "US-50 E": (1.7, 0.5), "MD-295 S": (-1.7, -0.2),
    "MD-2 S": (1.1, -1.35), "MD-27 NW": (-1.6, 0.4), "MD-140 NW": (-1.6, 0.5),
    "MD-97 N": (-0.6, 1.4), "Deep Run Rd": (0.3, 1.4), "Castleton Rd": (-0.3, 1.4),
    "Superior St": (1.6, -0.4), "I-70 W": (-1.6, -0.6), "US-29": (-1.7, 0.2),
    "MD-3 S": (-1.5, -0.9), "MD-4 S": (1.6, 0.9), "MD-4 (ramp)": (1.7, -0.7),
}


def fig_gateways(cty, study):
    g = pd.read_csv(GW)
    g["label"] = g.road.map(GW_SHORT).fillna(g.road.str.title())
    g["seeded"] = g.external > 0
    xs = np.concatenate([g.cx.to_numpy(), study.total_bounds[[0, 2]]])
    ys = np.concatenate([g.cy.to_numpy(), study.total_bounds[[1, 3]]])
    padx = 0.17 * (xs.max() - xs.min()); pady = 0.13 * (ys.max() - ys.min())
    bbox = (xs.min() - padx, ys.min() - pady, xs.max() + padx, ys.max() + pady)
    net = gpd.read_file(GPKG, layer="network", bbox=bbox).to_crs(CRS)

    w = ps.TEXTWIDTH_IN
    h = w * (bbox[3] - bbox[1]) / (bbox[2] - bbox[0])
    fig, ax = plt.subplots(figsize=(w, h))
    basemap(ax, cty, study, net, bbox)
    road_labels(ax, bbox)
    seeded = g[g.seeded]; zero = g[~g.seeded]
    ax.scatter(zero.cx, zero.cy, s=90, marker="*", facecolor="white", edgecolors=ps.OBS,
               linewidths=1.1, zorder=8)
    ax.scatter(seeded.cx, seeded.cy, s=105, marker="*", color=ps.OBS, edgecolors="white",
               linewidths=0.7, zorder=8)
    ax.scatter([c[0] for c in CROSSINGS], [c[1] for c in CROSSINGS], s=54, marker="o",
               color=HARBOR, edgecolors="white", linewidths=0.7, zorder=8)
    B = 34
    for _, r in g.iterrows():
        dx, dy = GW_OFF.get(r.label, (1.4, 1.0))
        ax.annotate(r.label, (r.cx, r.cy), xytext=(dx * B, dy * B), textcoords="offset points",
                    fontsize=7.2, ha="center", va="center", color="#1a1a1a", zorder=9,
                    bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="#B9B2A0", lw=0.5,
                              alpha=0.93),
                    arrowprops=dict(arrowstyle="-", lw=0.5, color="#6b6b6b",
                                    shrinkA=1.5, shrinkB=2.5))
    decorate(ax, bbox, 20000, "20 km", arrow="bl")

    handles = [
        Line2D([0], [0], marker="*", color="none", markerfacecolor=ps.OBS,
               markeredgecolor="white", markersize=12, label="Gateway, through traffic seeded"),
        Line2D([0], [0], marker="*", color="none", markerfacecolor="white",
               markeredgecolor=ps.OBS, markersize=12, label="Gateway, no seeding (count met)"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=HARBOR,
               markeredgecolor="white", markersize=8, label="Tolled harbor crossing"),
        Line2D([0], [0], color=C_FREE, lw=1.6, label="Freeway / interstate"),
        Line2D([0], [0], color=C_ART, lw=1.2, label="Arterial"),
        Line2D([0], [0], color=C_COLL, lw=1.0, label="Collector"),
        Line2D([0], [0], color=C_LOCAL, lw=0.8, label="Local street"),
        Patch(facecolor=STUDY_FILL, edgecolor="#5B8FB4", label="Assignment region")]
    ax.legend(handles=handles, loc="lower right", frameon=True, framealpha=0.93,
              edgecolor="#B9B2A0", fontsize=7.3, borderpad=0.5, handletextpad=0.6,
              labelspacing=0.35)
    fig.subplots_adjust(left=0.005, right=0.995, top=0.995, bottom=0.005)
    ps.save(fig, str(OUT / "map_gateways"))


def fig_screenlines(cty, study):
    d = pd.read_csv(SL)
    d["key"] = d.screenline.str.strip().str[0]
    xs = np.concatenate([d.x.to_numpy(), [c[0] for c in CROSSINGS], study.total_bounds[[0, 2]]])
    ys = np.concatenate([d.y.to_numpy(), [c[1] for c in CROSSINGS], study.total_bounds[[1, 3]]])
    padx = 0.10 * (xs.max() - xs.min()); pady = 0.06 * (ys.max() - ys.min())
    bbox = (xs.min() - padx, ys.min() - pady, xs.max() + padx, ys.max() + pady)
    net = gpd.read_file(GPKG, layer="network", bbox=bbox).to_crs(CRS)

    w = ps.TEXTWIDTH_IN
    h = w * (bbox[3] - bbox[1]) / (bbox[2] - bbox[0])
    fig, ax = plt.subplots(figsize=(w, h))
    basemap(ax, cty, study, net, bbox)
    road_labels(ax, bbox)

    # direct label offsets (data units) for each screenline
    LOFF = {"A": (0.055, -0.02), "B": (0.055, 0.02), "C": (-0.02, 0.06),
            "D": (0.055, -0.015), "E": (0.0, 0.06)}
    W, H = bbox[2] - bbox[0], bbox[3] - bbox[1]
    for k, grp in d.groupby("key"):
        col = SL_COLOR[k]
        x, y = grp.x.to_numpy(), grp.y.to_numpy()
        horiz = x.max() - x.min() >= y.max() - y.min()
        if horiz:
            m = 0.03 * W
            ax.plot([x.min() - m, x.max() + m], [np.median(y)] * 2, color=col, lw=2.4,
                    zorder=5, solid_capstyle="round")
            lx, ly = x.max() + m, np.median(y)
        else:
            m = 0.03 * H
            ax.plot([np.median(x)] * 2, [y.min() - m, y.max() + m], color=col, lw=2.4,
                    zorder=5, solid_capstyle="round")
            lx, ly = np.median(x), y.max() + m
        ax.scatter(x, y, s=15, color=col, edgecolors="white", linewidths=0.4, zorder=6)
        ox, oy = LOFF[k]
        ax.annotate(f"{k}. {SL_LABEL[k]}", (lx, ly), xytext=(lx + ox * W, ly + oy * H),
                    fontsize=7.6, fontweight="bold", color=col, ha="center", va="center",
                    zorder=8, bbox=dict(boxstyle="round,pad=0.24", fc="white", ec=col,
                                        lw=0.8, alpha=0.95))
    ax.scatter([c[0] for c in CROSSINGS], [c[1] for c in CROSSINGS], s=44, marker="D",
               color=SL_COLOR["A"], edgecolors="white", linewidths=0.6, zorder=7)
    decorate(ax, bbox, 20000, "20 km", arrow="tr")

    handles = [Line2D([0], [0], marker="o", color="none", markerfacecolor="0.35",
                      markeredgecolor="white", markersize=6, label="Captured AADT count station"),
               Line2D([0], [0], marker="D", color="none", markerfacecolor=SL_COLOR["A"],
                      markeredgecolor="white", markersize=6, label="Harbor toll crossing"),
               Line2D([0], [0], color=C_FREE, lw=1.6, label="Freeway / interstate"),
               Line2D([0], [0], color=C_ART, lw=1.2, label="Arterial"),
               Line2D([0], [0], color=C_COLL, lw=1.0, label="Collector"),
               Line2D([0], [0], color=C_LOCAL, lw=0.8, label="Local street")]
    ax.legend(handles=handles, loc="lower right", frameon=True, framealpha=0.93,
              edgecolor="#B9B2A0", fontsize=7.3, borderpad=0.5, handletextpad=0.6,
              labelspacing=0.35)
    fig.subplots_adjust(left=0.005, right=0.995, top=0.995, bottom=0.005)
    ps.save(fig, str(OUT / "map_screenlines"))


if __name__ == "__main__":
    cty, study = load_base()
    fig_gateways(cty, study)
    fig_screenlines(cty, study)
