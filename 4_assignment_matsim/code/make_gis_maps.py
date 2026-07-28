#!/usr/bin/env python3
"""Part B: map-based GIS validation of the MATSim transit-fix base vs AADT 2023.

Produces 5 TRB-quality maps into network_validation_2023/figures_transitfix/gis/
(600 dpi PNG + PDF):
  1_bmr_validation_map   - matched AADT points, colour=signed rel_err, size=obs AADT
  2_link_ratio_map       - matched links coloured by MATSim/AADT ratio (diverging @1.0)
  3_i695_beltway         - I-695 loop bold + per-count model-vs-observed
  4_county_choropleth    - median |rel_err| by BMR county
  5_matching_qa          - snap distance + flagged pre-fix bad matches highlighted

Context = the MATSim car network (thin grey). contextily basemap used if importable.
Uses the CLEANED validation CSV from Part A for the headline maps; the ORIGINAL CSV is
used in map 5 to show the bad matches that the fix removed.
"""
import os, gzip, re
os.environ.setdefault("NETVAL_OUTDIR", "scenarios/01_base_no_pricing/output_transitfix")
os.environ.setdefault("NETVAL_ITER", "64")
os.environ.setdefault("NETVAL_SUB", "transitfix")

import numpy as np, pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.cm import ScalarMappable
from netval2023_common import ROOT, OUTDIR, CRS, parse_network, load_linkstats

try:
    import contextily as cx
    HAS_CX = True
except Exception:
    HAS_CX = False

# figures go to the top-level figures_transitfix/ (not the per-run OUTDIR subdir)
GIS = ROOT/"network_validation_2023/figures_transitfix/gis"
GIS.mkdir(parents=True, exist_ok=True)
CLEAN = OUTDIR/"aadt/aadt_validation_2023_cleaned.csv"
ORIG  = OUTDIR/"aadt/aadt_validation_2023.csv"
COUNTIES = ROOT/"data/bmr_counties.gpkg"
BOUNDARY = ROOT/"validation/gis/bmr_boundary.gpkg"
I695_TXT = ROOT/"scenarios/toll_research/i695_link_ids.txt"

SKELETON_HWY = {"motorway","motorway_link","trunk","trunk_link","primary","primary_link",
                "secondary","secondary_link"}
mpl.rcParams.update({"font.size":11, "axes.titlesize":15, "axes.titleweight":"bold",
                     "savefig.dpi":600, "figure.dpi":120})


def save(fig, name):
    for ext in ("png","pdf"):
        fig.savefig(GIS/f"{name}.{ext}", dpi=600, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", GIS/f"{name}.png", "/ .pdf")


def build_network():
    """id->geometry / hwy / cap / vol24, plus a skeleton GeoDataFrame for context."""
    print("parsing network ...")
    nodes, links = parse_network()
    ls = load_linkstats()
    vol = ls["vol24"].to_dict()
    geom, hwy, cap, v = {}, {}, {}, {}
    sk_rows = []
    for l in links:
        if l["from"] not in nodes or l["to"] not in nodes: continue
        a, b = nodes[l["from"]], nodes[l["to"]]
        g = LineString([a, b]); lid = l["id"]
        geom[lid] = g; hwy[lid] = l["hwy"]; cap[lid] = l["cap"]; v[lid] = float(vol.get(lid, 0.0))
        if l["hwy"] in SKELETON_HWY:
            sk_rows.append({"hwy": l["hwy"], "geometry": g})
    sk = gpd.GeoDataFrame(sk_rows, geometry="geometry", crs=CRS)
    print(f"  links {len(geom):,}  skeleton (arterial+) {len(sk):,}")
    return geom, hwy, cap, v, sk


def pts_gdf(df):
    df = df.copy()
    df["geometry"] = [Point(x, y) for x, y in zip(df.lon, df.lat)]
    return gpd.GeoDataFrame(df, geometry="geometry", crs=CRS)


def basemap(ax):
    if HAS_CX:
        try:
            cx.add_basemap(ax, crs=CRS, source=cx.providers.CartoDB.PositronNoLabels, attribution_size=5)
            return True
        except Exception:
            pass
    return False


def draw_skeleton(ax, sk, alpha=0.35, lw=0.25, color="0.6"):
    sk.plot(ax=ax, color=color, linewidth=lw, alpha=alpha, zorder=1)


def set_extent(ax, gdf, pad=5000):
    minx, miny, maxx, maxy = gdf.total_bounds
    ax.set_xlim(minx-pad, maxx+pad); ax.set_ylim(miny-pad, maxy+pad)


# ---------------------------------------------------------------- Figure 1
def fig1_validation(sk, counties, boundary):
    df = pd.read_csv(CLEAN)
    d = pts_gdf(df[(df.facility != "Ramp") & (df.model_daily > 0)].copy())
    d["srel"] = d.rel_err_pct.clip(-100, 100)
    d["ms"] = 8 + 90*np.sqrt(d.obs_AADT/ d.obs_AADT.max())   # size ~ sqrt(obs AADT)
    fig, ax = plt.subplots(figsize=(11, 12))
    boundary.boundary.plot(ax=ax, color="0.15", linewidth=1.1, zorder=2)
    counties.boundary.plot(ax=ax, color="0.55", linewidth=0.6, linestyle="--", zorder=2)
    if not basemap(ax): draw_skeleton(ax, sk)
    sc = ax.scatter(d.geometry.x, d.geometry.y, c=d.srel, s=d.ms, cmap="RdBu",
                    vmin=-100, vmax=100, edgecolor="k", linewidth=0.25, alpha=0.9, zorder=3)
    cb = fig.colorbar(sc, ax=ax, shrink=0.5, pad=0.01)
    cb.set_label("Signed relative error  (model - obs)/obs  [%]\nred = model UNDER   |   blue = model OVER")
    # obs-AADT size legend
    for a in [5000, 50000, 150000]:
        ax.scatter([], [], s=8+90*np.sqrt(a/df.obs_AADT.max()), c="0.5",
                   edgecolor="k", linewidth=0.25, label=f"{a:,} AADT")
    ax.legend(title="Observed AADT", loc="lower left", frameon=True, labelspacing=1.4, borderpad=1.0)
    ax.set_title("MATSim base (transit-fixed) vs MDOT SHA AADT 2023 — BMR\nmatched mainline count stations (ramps excluded)")
    set_extent(ax, counties)
    ax.set_axis_off()
    n = len(d); mb = df[(df.facility!='Ramp')&(df.model_daily>0)].rel_err_pct.median()
    ax.annotate(f"n = {n:,} stations   median rel_err = {mb:+.0f}%",
                xy=(0.99,0.01), xycoords="axes fraction", ha="right", fontsize=10,
                bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.9))
    save(fig, "1_bmr_validation_map")


# ---------------------------------------------------------------- Figure 2
def fig2_link_ratio(geom, sk, boundary, counties):
    df = pd.read_csv(CLEAN)
    d = df[(df.facility != "Ramp") & (df.model_daily > 0)].copy()
    rows = []
    for _, r in d.iterrows():
        ratio = r.model_daily/r.obs_AADT if r.obs_AADT > 0 else np.nan
        for lid in str(r.link_ids).split(";"):
            if lid in geom: rows.append({"ratio": ratio, "geometry": geom[lid]})
    lg = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)
    lg["ratio"] = lg.ratio.clip(0.25, 4.0)
    fig, ax = plt.subplots(figsize=(11, 12))
    boundary.boundary.plot(ax=ax, color="0.15", linewidth=1.1, zorder=2)
    if not basemap(ax): draw_skeleton(ax, sk, alpha=0.25, lw=0.2)
    norm = TwoSlopeNorm(vmin=0.25, vcenter=1.0, vmax=4.0)
    lg.plot(ax=ax, column="ratio", cmap="RdBu", norm=norm, linewidth=1.7, zorder=3)
    sm = ScalarMappable(norm=norm, cmap="RdBu"); sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, shrink=0.5, pad=0.01, extend="both")
    cb.set_label("MATSim / AADT ratio\n<1 model UNDER (red)   |   >1 model OVER (blue)")
    cb.set_ticks([0.25,0.5,1.0,2.0,4.0]); cb.set_ticklabels(["0.25","0.5","1.0","2.0","4.0"])
    counties.boundary.plot(ax=ax, color="0.55", linewidth=0.6, linestyle="--", zorder=2)
    ax.set_title("Matched-link assignment ratio — MATSim base vs AADT 2023\n(diverging scale centred at 1.0)")
    set_extent(ax, counties)
    ax.set_axis_off()
    save(fig, "2_link_ratio_map")


# ---------------------------------------------------------------- Figure 3
def fig3_i695(geom, vol, sk, boundary):
    ids = [ln.strip() for ln in open(I695_TXT) if ln.strip() and not ln.startswith("#")]
    ids = [i for i in ids if i in geom]
    i695 = gpd.GeoDataFrame({"geometry":[geom[i] for i in ids]}, geometry="geometry", crs=CRS)
    df = pd.read_csv(CLEAN)
    idset = set(ids)
    on = df[df.link_ids.fillna("").apply(lambda s: any(l in idset for l in s.split(";")))].copy()
    on = pts_gdf(on[on.model_daily > 0])
    fig, ax = plt.subplots(figsize=(11, 11))
    minx,miny,maxx,maxy = i695.total_bounds; pad=6000
    ax.set_xlim(minx-pad, maxx+pad); ax.set_ylim(miny-pad, maxy+pad)
    if not basemap(ax): draw_skeleton(ax, sk, alpha=0.4, lw=0.3)
    i695.plot(ax=ax, color="#111111", linewidth=3.2, zorder=3, label="I-695 Beltway")
    if len(on):
        on["srel"] = on.rel_err_pct.clip(-100,100)
        on["ms"] = 40 + 260*np.sqrt(on.obs_AADT/on.obs_AADT.max())
        sc = ax.scatter(on.geometry.x, on.geometry.y, c=on.srel, s=on.ms, cmap="RdBu",
                        vmin=-100, vmax=100, edgecolor="k", linewidth=0.7, zorder=4)
        cb = fig.colorbar(sc, ax=ax, shrink=0.5, pad=0.01)
        cb.set_label("Signed rel_err [%]  (red = model under / blue = over)")
    tot_m = on.model_daily.sum(); tot_o = on.obs_AADT.sum()
    ax.set_title("I-695 Baltimore Beltway — toll-corridor QA\nsize = observed AADT, colour = signed error at each mainline count")
    handles = [Line2D([],[],marker='o',color='w',markerfacecolor='0.6',markeredgecolor='k',markersize=ms,label=lab)
               for ms,lab in [(7,"50k AADT"),(13,"120k AADT"),(18,"200k AADT")]]
    handles = [Line2D([],[],color="#111111",lw=3,label="I-695 Beltway")] + handles
    ax.legend(handles=handles, loc="upper right", frameon=True, labelspacing=1.3)
    ax.set_axis_off()
    ax.annotate(f"I-695 count stations: {len(on)}   corridor Σmodel/Σobs = {tot_m/tot_o:.2f}"
                if tot_o>0 else f"I-695 count stations: {len(on)}",
                xy=(0.5,0.005), xycoords="axes fraction", ha="center", fontsize=10,
                bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.9))
    save(fig, "3_i695_beltway")
    return len(on), tot_m, tot_o


# ---------------------------------------------------------------- Figure 4
def fig4_county(counties, boundary):
    df = pd.read_csv(CLEAN)
    d = df[(df.facility != "Ramp") & (df.model_daily > 0)].copy()
    d["arel"] = (d.rel_err_pct).abs()
    agg = d.groupby("COUNTY_DESC").agg(med_absrel=("arel","median"),
                                       n=("arel","size"),
                                       medbias=("rel_err_pct","median")).reset_index()
    c = counties.merge(agg, on="COUNTY_DESC", how="left")
    fig, ax = plt.subplots(figsize=(11, 11))
    c.plot(ax=ax, column="med_absrel", cmap="YlOrRd", linewidth=0.8, edgecolor="0.3",
           legend=True, vmin=20, vmax=60,
           legend_kwds={"label":"median |relative error| [%]","shrink":0.5})
    boundary.boundary.plot(ax=ax, color="0.15", linewidth=1.0, zorder=2)
    for _, r in c.iterrows():
        cen = r.geometry.representative_point()
        lbl = f"{r.COUNTY_DESC.title()}\n{r.med_absrel:.0f}%  (n={int(r.n)})" if pd.notna(r.med_absrel) else r.COUNTY_DESC.title()
        ax.annotate(lbl, (cen.x, cen.y), ha="center", va="center", fontsize=9,
                    bbox=dict(boxstyle="round", fc="white", ec="0.5", alpha=0.85))
    ax.set_title("Median |relative error| by BMR county — MATSim base vs AADT 2023\n(mainline, ramps excluded)")
    ax.set_axis_off()
    save(fig, "4_county_choropleth")
    return agg


# ---------------------------------------------------------------- Figure 5
def fig5_matching_qa(sk, boundary, counties):
    o = pd.read_csv(ORIG)
    new = pd.read_csv(CLEAN)
    d = pts_gdf(o[(o.facility != "Ramp") & (o.model_daily > 0)].copy())
    d["ratio"] = d.model_daily/d.obs_AADT
    # flagged bad matches (pre-fix): far snap OR gross over-prediction that the fix removed
    newmatched = set(new[new.model_daily > 0].LOCATION_ID)
    d["dropped"] = ~d.LOCATION_ID.isin(newmatched)
    d["flag"] = d.dropped | ((d.min_dist > 25) & (d.ratio > 3))
    fig, ax = plt.subplots(figsize=(11, 12))
    boundary.boundary.plot(ax=ax, color="0.15", linewidth=1.0, zorder=2)
    if not basemap(ax): draw_skeleton(ax, sk)
    good = d[~d.flag]
    sc = ax.scatter(good.geometry.x, good.geometry.y, c=good.min_dist.clip(0,40), s=14,
                    cmap="viridis", vmin=0, vmax=40, edgecolor="none", alpha=0.85, zorder=3)
    cb = fig.colorbar(sc, ax=ax, shrink=0.5, pad=0.01)
    cb.set_label("snap distance to matched link [m]")
    bad = d[d.flag]
    ax.scatter(bad.geometry.x, bad.geometry.y, s=70, facecolor="none", edgecolor="red",
               linewidth=1.4, zorder=4, label=f"flagged bad match (removed by fix), n={len(bad)}")
    counties.boundary.plot(ax=ax, color="0.55", linewidth=0.6, linestyle="--", zorder=2)
    ax.set_title("Matching QA — snap distance + flagged pre-fix bad matches\nmajor network snaps at ~1 m (dark); flagged = far/parallel-road grabs removed by fix")
    ax.legend(loc="lower left", frameon=True)
    set_extent(ax, counties)
    ax.set_axis_off()
    save(fig, "5_matching_qa")
    return int(d.flag.sum())


def main():
    counties = gpd.read_file(COUNTIES)
    boundary = gpd.read_file(BOUNDARY)
    geom, hwy, cap, vol, sk = build_network()
    print("Figure 1 ..."); fig1_validation(sk, counties, boundary)
    print("Figure 2 ..."); fig2_link_ratio(geom, sk, boundary, counties)
    print("Figure 3 ..."); n695, m695, o695 = fig3_i695(geom, vol, sk, boundary)
    print("Figure 4 ..."); agg = fig4_county(counties, boundary)
    print("Figure 5 ..."); nflag = fig5_matching_qa(sk, boundary, counties)
    print(f"\ncontextily basemap: {'YES' if HAS_CX else 'NO (network skeleton used)'}")
    print(f"I-695: {n695} count stations, corridor model/obs = {m695/o695:.2f}" if o695 else f"I-695: {n695} stations")
    print("\ncounty median |rel_err|:")
    print(agg.to_string(index=False))
    print(f"\nflagged bad matches shown on QA map: {nflag}")
    print(f"\nall maps -> {GIS}")


if __name__ == "__main__":
    main()
