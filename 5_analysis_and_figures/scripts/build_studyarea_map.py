#!/usr/bin/env python3
"""Study-area map for the TRB paper (two panels).

(a) The full MSTM region over which population synthesis and land use are simulated.
(b) The six-jurisdiction Baltimore assignment region loaded in MATSim, with its
    freeway network.

All geometry comes from the validation GeoPackage used by the other MATSim map
figures (EPSG:26985).
"""
from __future__ import annotations
import sys
from pathlib import Path
import geopandas as gpd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_style as ps
ps.apply()
import matplotlib.pyplot as plt
plt.rcParams['savefig.dpi'] = 300
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

GPKG = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
            "/network_validation_2023/v7_base/gis/bmr_validation.gpkg")
OUT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"
           "/Paper Figures Final/figures")
OUT.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:26985"

STUDY = ["Baltimore City, MD", "Baltimore County, MD", "Anne Arundel County, MD",
         "Howard County, MD", "Harford County, MD", "Carroll County, MD"]

LAND = "#FFFFFF"
LAND_EDGE = "#C8C1B0"
STATE_EDGE = "#8A8271"
STUDY_FILL = "#E7F1FA"
FREEWAY = "#2C4A63"


def scalebar(ax, length_m, label, frac_x=0.06, frac_y=0.05):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x0 + frac_x * (x1 - x0)
    y = y0 + frac_y * (y1 - y0)
    ax.plot([x, x + length_m], [y, y], color="black", lw=2.0, solid_capstyle="butt", zorder=8)
    ax.text(x + length_m / 2, y + 0.015 * (y1 - y0), label, ha="center", va="bottom",
            fontsize=7.5, zorder=8)


def main():
    cty = gpd.read_file(GPKG, layer="county_boundaries").to_crs(CRS)
    study = cty[cty.JUR_NAME.isin(STUDY)].copy()

    minx, miny, maxx, maxy = study.total_bounds
    pad = 0.10 * max(maxx - minx, maxy - miny)
    sb = (minx - pad, miny - pad, maxx + pad, maxy + pad)

    net = gpd.read_file(GPKG, layer="network", bbox=sb).to_crs(CRS)
    fw = net[net["facility"].astype(str).str.contains("Freeway", case=False, na=False)]
    _hw = net.highway.astype(str)
    FREE = {"motorway","motorway_link","trunk","trunk_link"}
    ART = {"primary","primary_link","secondary","secondary_link"}
    COLL = {"tertiary","tertiary_link","unclassified"}

    fig, axs = plt.subplots(1, 2, figsize=(ps.TEXTWIDTH_IN, ps.TEXTWIDTH_IN * 0.50))

    # ---- (a) full MSTM modeling region -------------------------------------
    ax = axs[0]
    cty.plot(ax=ax, color=LAND, edgecolor=LAND_EDGE, linewidth=0.25, zorder=1, rasterized=True)
    cty.dissolve(by="STFIPS").boundary.plot(ax=ax, color=STATE_EDGE, linewidth=0.7, zorder=2, rasterized=True)
    study.plot(ax=ax, color=STUDY_FILL, edgecolor=ps.SIM, linewidth=0.5, zorder=3, rasterized=True)
    ax.add_patch(Rectangle((sb[0], sb[1]), sb[2] - sb[0], sb[3] - sb[1],
                           fill=False, edgecolor=ps.OBS, linewidth=1.1, zorder=4))
    ax.set_title("(a) Land-use modeling region (MSTM)", loc="left",
                 fontsize=9.5, fontweight="bold")
    ax.set_aspect("equal")
    ax.set_axis_off()
    scalebar(ax, 100000, "100 km")

    # ---- (b) assignment region ---------------------------------------------
    ax = axs[1]
    cty.plot(ax=ax, color=LAND, edgecolor=LAND_EDGE, linewidth=0.4, zorder=1, rasterized=True)
    study.plot(ax=ax, color=STUDY_FILL, edgecolor=ps.SIM, linewidth=0.7, zorder=2, rasterized=True)
    net[~_hw.isin(FREE|ART|COLL)].plot(ax=ax, color="#CDD2D8", linewidth=0.16, zorder=2.4, rasterized=True)
    net[_hw.isin(COLL)].plot(ax=ax, color="#AEB8C2", linewidth=0.30, zorder=2.5, rasterized=True)
    net[_hw.isin(ART)].plot(ax=ax, color="#7E93A8", linewidth=0.55, zorder=2.7, rasterized=True)
    net[_hw.isin(FREE)].plot(ax=ax, color=FREEWAY, linewidth=0.9, zorder=3, rasterized=True)
    for _, r in study.iterrows():
        p = r.geometry.representative_point()
        name = r.JUR_NAME.replace(" County, MD", "").replace(", MD", "")
        ax.annotate(name, (p.x, p.y), ha="center", va="center", fontsize=8.0,
                    fontweight="bold", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="none", alpha=0.75))
    ax.set_xlim(sb[0], sb[2])
    ax.set_ylim(sb[1], sb[3])
    ax.set_title("(b) Dynamic assignment region", loc="left",
                 fontsize=9.5, fontweight="bold")
    ax.set_aspect("equal")
    ax.set_axis_off()
    scalebar(ax, 20000, "20 km")
    nx = sb[2] - 0.08 * (sb[2] - sb[0])
    ny = sb[3] - 0.20 * (sb[3] - sb[1])
    ax.annotate("N", xy=(nx, ny + 0.10 * (sb[3] - sb[1])), xytext=(nx, ny),
                ha="center", va="bottom", fontsize=9, fontweight="bold", zorder=8,
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1.1))

    handles = [Patch(facecolor=STUDY_FILL, edgecolor=ps.SIM,
                     label="Assignment region (six jurisdictions)"),
               Patch(facecolor=LAND, edgecolor=LAND_EDGE, label="Modeling region counties"),
               Line2D([0], [0], color=ps.OBS, lw=1.1, label="Extent of panel (b)"),
               Line2D([0], [0], color=FREEWAY, lw=1.2, label="Freeway / interstate"),
               Line2D([0], [0], color="#7E93A8", lw=1.0, label="Arterial / collector / local")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
               fontsize=8.2, bbox_to_anchor=(0.5, 0.0))

    fig.tight_layout(rect=(0, 0.10, 1, 1))
    ps.save(fig, str(OUT / "study_area_map"))


if __name__ == "__main__":
    main()
