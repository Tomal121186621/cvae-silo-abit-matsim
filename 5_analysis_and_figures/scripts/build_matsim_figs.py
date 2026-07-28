#!/usr/bin/env python3
"""Build the MATSim validation figures for the TRB paper.

Seven exhibits, all written to  Paper Figures Final/figures/matsim/ .
Every plotted number is read from the real CSV / scorestats / linkstats data produced by
the MATSim run and its validation pipeline (no hand-entered values).  Dense geospatial
maps and the 2000+ point all-station scatter — which cannot be faithfully re-plotted from
a flat CSV — are EMBEDDED as their published PNGs (imshow, axis off, bold panel letter).

Uniform look comes from the paper-wide paper_style module (matches figures/vae/*, figures/silo/*).

  1 matsim_convergence.pdf   RE-PLOT scorestats.csv (score by iteration)
  2 matsim_gateways.pdf      EMBED  F5_gateway_seed_map.png
  3 matsim_counts.pdf        (a) EMBED fig8_all_stations_50pct.png  (b) RE-PLOT i695 scatter
  4 matsim_tmas_hourly.pdf   RE-PLOT TMAS hourly profiles at 8 I-695 corridor stations
  5 matsim_modeshare.pdf     (a) RE-PLOT overall shares + NTD  (b) RE-PLOT transit share by purpose
  6 matsim_screenline_map.pdf EMBED figS1_screenline_map.png
  7 matsim_screenline_val.pdf RE-PLOT screenline_summary.csv (obs vs model crossing volumes)
"""
from __future__ import annotations
import os, sys, re, gzip
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_style as ps
ps.apply()
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image

MAT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
FIG = MAT / "trb_paper" / "figures"
SCORE = MAT / "scenarios/01_base_no_pricing/output_base_v17mc/scorestats.csv"
OUT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"
           "/Paper Figures Final/figures/matsim")
OUT.mkdir(parents=True, exist_ok=True)

# a distinct third colour for the ABIT / intermediate series (keeps OBS=orange, SIM=blue)
ABIT_C = ps.NEUTRAL

STATS = {}   # headline numbers collected for the report


def embed(ax, png, letter=None):
    """Draw a published PNG into ax as a crisp raster, no axes/caption."""
    ax.imshow(np.asarray(Image.open(png)))
    ax.axis("off")
    if letter is not None:
        ax.text(0.01, 0.99, letter, transform=ax.transAxes, va="top", ha="left",
                fontsize=11, fontweight="bold")


# ------------------------------------------------------------------ 1. convergence
def fig_convergence():
    df = pd.read_csv(SCORE, sep=";")
    it = df["iteration"].to_numpy()
    fig, ax = plt.subplots(figsize=(ps.TEXTWIDTH_IN, ps.TEXTWIDTH_IN * 0.52))
    ax.plot(it, df["avg_best"],     color=ps.TARGET,  lw=1.4, label="Best plan")
    ax.plot(it, df["avg_executed"], color=ps.SIM,     lw=2.2, label="Executed (selected)")
    ax.plot(it, df["avg_average"],  color=ps.NEUTRAL, lw=1.4, label="Average plan")
    ax.plot(it, df["avg_worst"],    color=ps.OBS,     lw=1.4, ls="--", label="Worst plan")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Average plan score")
    ax.set_title("MATSim co-evolutionary convergence")
    ax.legend(ncol=2, loc="lower right")
    ax.set_xlim(it.min(), it.max())
    fig.tight_layout()
    ps.save(fig, str(OUT / "matsim_convergence"))
    STATS["convergence"] = dict(iters=int(it.max()),
                                exec_final=float(df["avg_executed"].iloc[-1]),
                                exec_start=float(df["avg_executed"].iloc[0]))


# ------------------------------------------------------------------ 2. gateways map
def fig_gateways():
    fig, ax = plt.subplots(figsize=(ps.TEXTWIDTH_IN, ps.TEXTWIDTH_IN * 0.73))
    embed(ax, FIG / "F5_gateway_seed_map.png")
    fig.tight_layout()
    ps.save(fig, str(OUT / "matsim_gateways"))


# ------------------------------------------------------------------ 3. counts
def _i695_scatter(ax):
    d = pd.read_csv(FIG / "counts_passenger" / "i695_station_validation.csv")
    SUSPECT = {"B1197", "T0006", "B1198", "B1093", "B1096", "P0074", "B1095"}
    d = d[~d.LOCATION_ID.isin(SUSPECT)]
    obs = d.obs_AADT.to_numpy() / 1e3
    sim = d.m.to_numpy() / 1e3
    r2 = float(np.corrcoef(obs, sim)[0, 1] ** 2)
    ratio = float(sim.sum() / obs.sum())
    w50 = float(100 * (np.abs((sim - obs) / obs) <= 0.50).mean())
    xx = np.array([1.0, 400.0])
    ax.plot(xx, xx, color=ps.NEUTRAL, lw=1.1, zorder=2, label="1:1")
    ax.plot(xx, 1.50 * xx, color=ps.NEUTRAL, ls=":", lw=0.9, zorder=2)
    ax.plot(xx, 0.50 * xx, color=ps.NEUTRAL, ls=":", lw=0.9, zorder=2, label="±50% band")
    ax.scatter(obs, sim, s=30, color=ps.SIM, edgecolors="white", linewidth=0.6,
               alpha=0.9, zorder=3, label="I-695 station")
    ax.annotate(f"n = {len(d)} stations\n$R^2$ = {r2:.2f}\n"
                f"$\\Sigma$sim/$\\Sigma$obs = {ratio:.2f}\nwithin ±50%: {w50:.0f}%",
                (0.04, 0.87), xycoords="axes fraction", va="top", ha="left", fontsize=8,
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="0.7", lw=0.6))
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(40, 280); ax.set_ylim(40, 280); ax.set_aspect("equal")
    tks = [50, 100, 150, 200, 250]
    ax.set_xticks(tks); ax.set_yticks(tks)
    fmt = plt.FuncFormatter(lambda v, _: f"{v:g}")
    ax.xaxis.set_major_formatter(fmt); ax.yaxis.set_major_formatter(fmt)
    ax.minorticks_off()
    ax.set_xlabel("Observed AADT (1000 veh/day)")
    ax.set_ylabel("Simulated volume (1000 veh/day)")
    ax.set_title("I-695 corridor stations")
    ax.legend(frameon=False, fontsize=7.5, loc="lower right")
    STATS["i695"] = dict(n=int(len(d)), r2=r2, ratio=ratio, within50=w50)


def fig_counts():
    fig, axs = plt.subplots(1, 2, figsize=(ps.TEXTWIDTH_IN, ps.TEXTWIDTH_IN * 0.50))
    embed(axs[0], FIG / "counts_passenger" / "fig8_all_stations_50pct.png", letter="(a)")
    axs[0].set_title("All mainline count stations")
    _i695_scatter(axs[1])
    ps.panel_letter(axs[1], 1)
    fig.tight_layout()
    ps.save(fig, str(OUT / "matsim_counts"))


# ------------------------------------------------------------------ 4. TMAS hourly
def fig_tmas():
    LS = MAT / "scenarios/01_base_no_pricing/output_calib_fs/pass8/ITERS/it.10/10.linkstats.txt.gz"
    TMAS = MAT / "network_validation_2023" / "tmas"
    STATIONS = [
        ("0P0032", "I-695 W"),
        ("0P0077", "I-695 SW"),
        ("0P0078", "I-695 NW"),
        ("0P0054", "I-695 NE"),
        ("0P0074", "I-695 E"),
        ("0P0071", "I-95 SW"),
        ("0P0052", "I-83 N"),
        ("0P0053", "I-70 W"),
    ]
    val = pd.read_csv(TMAS / "tmas_validation_2023.csv", dtype={"station_id": str})
    prof = pd.read_csv(TMAS / "station_profiles.csv",
                       dtype={"station_id": str}).set_index("station_id")
    ls = pd.read_csv(LS, sep="\t", low_memory=False)
    hrcols = [c for c in ls.columns
              if (m := re.fullmatch(r"HRS(\d+)-(\d+)avg", c)) and int(m[2]) - int(m[1]) == 1]
    hrcols.sort(key=lambda c: int(re.match(r"HRS(\d+)-", c).group(1)))
    assert len(hrcols) == 24, hrcols
    ls["LINK"] = ls["LINK"].astype(str)
    lk = ls.set_index("LINK")[hrcols]

    fig, axes = plt.subplots(2, 4, figsize=(ps.TEXTWIDTH_IN, ps.TEXTWIDTH_IN * 0.62),
                             sharex=True, sharey=True)
    rs = []
    for i, (ax, (sid, title)) in enumerate(zip(axes.flat, STATIONS)):
        row = val[val.station_id == sid].iloc[0]
        links = [l for l in str(row.link_ids).split(";") if l in lk.index]
        mod = lk.loc[links, hrcols].sum(axis=0).to_numpy() * 10.0
        obs = prof.loc[sid, [f"obs_h{h}" for h in range(24)]].to_numpy(float)
        obs_s, mod_s = obs / obs.sum(), mod / mod.sum()
        r = float(np.corrcoef(obs_s, mod_s)[0, 1]); rs.append(r)
        ax.plot(range(24), 100 * obs_s, color=ps.OBS, lw=1.3, label="Observed (TMAS 2023)")
        ax.plot(range(24), 100 * mod_s, color=ps.SIM, lw=1.3, label="Model (MATSim)")
        ax.set_title(f"({'abcdefgh'[i]}) {title}", loc="left", fontsize=9,
                     fontweight="bold", pad=3)
        ax.annotate(f"$r={r:.2f}$", (0.95, 0.90), xycoords="axes fraction",
                    ha="right", va="top", fontsize=8, fontweight="bold")
        ax.set_xticks([0, 6, 12, 18, 24])
    for ax in axes[1]:
        ax.set_xlabel("Hour of day")
    for ax in axes[:, 0]:
        ax.set_ylabel("Share of daily (%)")
    h, l = axes[0, 0].get_legend_handles_labels()
    ps.shared_legend(fig, h, l, ncol=2, y=1.02)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.subplots_adjust(wspace=0.18, hspace=0.42)
    ps.save(fig, str(OUT / "matsim_tmas_hourly"))
    STATS["tmas"] = dict(n=len(STATIONS), mean_r=float(np.mean(rs)))


# ------------------------------------------------------------------ 5. mode share
NTD_TRANSIT = 0.021   # NTD-2023-implied transit trip share (from make_modechoice_rts_validation.py)


ORDER = ["car", "ride", "pt", "walk", "bike"]
MLAB = ["Car\n(driver)", "Car\n(pass.)", "Transit", "Walk", "Bike"]
SRC_H = lambda: [plt.Rectangle((0, 0), 1, 1, color=c) for c in (ps.OBS, ABIT_C, ps.SIM)]
SRC_L = ["Observed (RTS)", "ABIT", "Model (MATSim)"]


def fig_modeshare():
    # ---- overall mode share (single panel) ----
    md = pd.read_csv(FIG / "modeshare" / "mode_validation_rts.csv").set_index("mode").loc[ORDER]
    fig, ax = plt.subplots(figsize=(ps.TEXTWIDTH_IN * 0.66, ps.TEXTWIDTH_IN * 0.42))
    ps.grouped_bar(ax, MLAB,
                   [("Observed (RTS)", md["rts"].to_numpy() * 100, ps.OBS),
                    ("ABIT",           md["abit"].to_numpy() * 100, ABIT_C),
                    ("Model (MATSim)", md["matsim"].to_numpy() * 100, ps.SIM)],
                   title=None, ylabel="Share of trips (%)", rotate=0)
    ps.shared_legend(fig, SRC_H(), SRC_L, ncol=3, y=1.04)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    ps.save(fig, str(OUT / "matsim_modeshare"))
    STATS["overall"] = {m: dict(rts=float(md.loc[m, "rts"]), abit=float(md.loc[m, "abit"]),
                                matsim=float(md.loc[m, "matsim"])) for m in ORDER}
    STATS["ntd_transit"] = NTD_TRANSIT


def fig_mode_by_purpose():
    # Combined mode-share validation (levels, survey/ABIT/MATSim): panel (a) all purposes,
    # then one panel per trip purpose. Legend occupies the sixth slot.
    md = pd.read_csv(FIG / "modeshare" / "mode_validation_rts.csv").set_index("mode").loc[ORDER]
    bp = pd.read_csv(FIG / "modeshare" / "mode_by_purpose.csv")
    purp = ["HBW", "HBS", "HBO", "NHB"]
    ptitle = {"HBW": "Home-based work", "HBS": "Home-based shopping",
              "HBO": "Home-based other", "NHB": "Non-home-based"}
    MLAB_C = ["Car\ndrv", "Car\npass", "PT", "Walk", "Bike"]
    fig, axs = plt.subplots(2, 3, figsize=(ps.TEXTWIDTH_IN, ps.TEXTWIDTH_IN * 0.60))
    axs = axs.ravel()
    ps.grouped_bar(axs[0], MLAB_C,
                   [("Observed (RTS)", md["rts"].to_numpy() * 100, ps.OBS),
                    ("ABIT",           md["abit"].to_numpy() * 100, ABIT_C),
                    ("Model (MATSim)", md["matsim"].to_numpy() * 100, ps.SIM)],
                   title="All purposes", ylabel="Share (%)", rotate=0)
    ps.panel_letter(axs[0], 0)
    for j, p in enumerate(purp):
        ax = axs[j + 1]
        d = bp[bp["purpose"] == p].set_index("mode").loc[ORDER]
        ps.grouped_bar(ax, MLAB_C,
                       [("Observed (RTS)", d["rhts"].to_numpy() * 100, ps.OBS),
                        ("ABIT",           d["abit"].to_numpy() * 100, ABIT_C),
                        ("Model (MATSim)", d["matsim"].to_numpy() * 100, ps.SIM)],
                       title=ptitle[p], ylabel="Share (%)", rotate=0)
        ps.panel_letter(ax, j + 1)
    axs[5].axis("off")
    axs[5].legend(SRC_H(), SRC_L, loc="center", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.subplots_adjust(hspace=0.45, wspace=0.38)
    ps.save(fig, str(OUT / "matsim_mode_by_purpose"))


# ------------------------------------------------------------------ 6. screenline map
def fig_screenline_map():
    fig, ax = plt.subplots(figsize=(ps.TEXTWIDTH_IN, ps.TEXTWIDTH_IN * 0.88))
    embed(ax, FIG / "screenlines" / "figS1_screenline_map.png")
    fig.tight_layout()
    ps.save(fig, str(OUT / "matsim_screenline_map"))


# ------------------------------------------------------------------ 7. screenline val
def fig_screenline_val():
    df = pd.read_csv(FIG / "screenlines" / "screenline_summary.csv")
    # drop the harbor line: it has no AADT count stations (validated via the count figures)
    df = df[~df["screenline"].str.contains("Patapsco")].reset_index(drop=True)
    # short labels: leading letter + first key word
    def short(s):
        p = s.split()
        return f"{p[0]}\n{' '.join(p[1:])}"
    labels = [short(s) for s in df["screenline"]]
    obs = df["obs"].to_numpy() / 1e3
    mod = df["model"].to_numpy() / 1e3
    fig, ax = plt.subplots(figsize=(ps.TEXTWIDTH_IN, ps.TEXTWIDTH_IN * 0.52))
    ps.grouped_bar(
        ax, labels,
        [("Observed (AADT)", obs, ps.OBS),
         ("Model (MATSim)",  mod, ps.SIM)],
        title="Screenline crossing volumes", ylabel="Crossing volume (1000 veh/day)",
        rotate=0)
    # annotate model/obs ratio above each pair
    for i, (o, m) in enumerate(zip(obs, mod)):
        ax.annotate(f"{m/o:.2f}×", (i, max(o, m)), textcoords="offset points",
                    xytext=(0, 3), ha="center", fontsize=7.5, color=ps.NEUTRAL)
    ax.legend(loc="upper right")
    fig.tight_layout()
    ps.save(fig, str(OUT / "matsim_screenline_val"))
    STATS["screenline"] = {r.screenline.split()[0]: dict(obs=int(r.obs), model=int(r.model),
                           ratio=float(r.model / r.obs), diff_pct=float(r.diff_pct))
                           for r in df.itertuples()}


def main():
    # convergence uses the original MATSim scorestats.png (embedded directly); do not regenerate
    # fig_convergence()
    fig_gateways()
    fig_counts()
    fig_tmas()
    fig_modeshare()
    fig_mode_by_purpose()
    fig_screenline_map()
    fig_screenline_val()
    print("\n=== HEADLINE NUMBERS ===")
    import json
    print(json.dumps(STATS, indent=2))


if __name__ == "__main__":
    main()
