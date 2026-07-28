#!/usr/bin/env python3
"""Publication-quality summary figures from a scenario's per-bin scorecard:
  1. scorecard heatmap  — states x variables, worst per-bin gap (pp) over the forecast window,
     diverging colormap centered on the 5pp acceptance threshold (<=5 green, >5 red).
  2. drift trajectory   — worst per-bin gap by year for each variable (mean over states), showing
     how the forecast error evolves 2016 -> 2023 against the 5pp band.

Usage: SILO_SCEN=updated_vae_calib2 OUT_SUB=by_year_acs_calib2 python make_summary_figures.py
Reads ../validation/<OUT_SUB>/perbin_scorecard.csv ; writes ../validation/<OUT_SUB>/figures/.
"""
from __future__ import annotations
import os
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import sys; sys.path.insert(0, "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/code")
import trb_style; trb_style.apply()

HERE = Path(__file__).resolve().parent
SCEN = os.environ.get("SILO_SCEN", "updated_vae_calib2")
OUT_SUB = os.environ.get("OUT_SUB", f"by_year_acs_{SCEN.replace('updated_vae_', '')}")
VALDIR = HERE.parent / "validation" / OUT_SUB
FIGDIR = VALDIR / "TRB_figures"   # TRB re-styled copy
ORIGDIR = VALDIR / "figures"      # original figure folder (kept in sync)
TOL = 5.0
STATES = ["MD", "VA", "PA", "DE", "DC", "WV"]
VARS = ["hhSize", "autos", "dwellingType", "hh_inc9", "age_bin", "gender", "occ_silo", "race4"]
VLAB = {"hhSize": "Household\nsize", "autos": "Autos", "dwellingType": "Dwelling\ntype",
        "hh_inc9": "HH income", "age_bin": "Age", "gender": "Gender",
        "occ_silo": "Occupation", "race4": "Race/\nethnicity"}


def _save_both(fig, name, cap):
    """Save a figure (with caption) as PNG+PDF into BOTH the original `figures/`
    folder and the TRB-styled `TRB_figures/` folder, then close it. Both copies
    carry the same fix so the deck/speaker-guide figures never diverge."""
    trb_style.caption(fig, cap)
    for d in (ORIGDIR, FIGDIR):
        d.mkdir(parents=True, exist_ok=True)
        fig.savefig(d / (name + ".png"), dpi=300, bbox_inches="tight", facecolor="white")
        fig.savefig(d / (name + ".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return (ORIGDIR / (name + ".png"), FIGDIR / (name + ".png"))


def _states_by_year(df):
    """Return {year: sorted[states]} so captions can disclose partial coverage."""
    return {int(y): sorted(g.state.unique()) for y, g in df.groupby("year")}


def heatmap(df):
    fc = df[df.year.between(2021, 2023)].groupby(["state", "variable"]).max_bin_pp.max().unstack()
    fc = fc.reindex(index=[s for s in STATES if s in fc.index],
                    columns=[v for v in VARS if v in fc.columns])
    M = fc.to_numpy(dtype=float)
    # Median-income bias (%) is NOT a per-bin gap, so the binned-income (hh_inc9)
    # cell can read green while the median dollar income is materially biased.
    # Surface the worst-magnitude signed median bias over the window next to that
    # cell so the two are never read in isolation (TRB audit M4).
    med_bias = {}
    try:
        s = pd.read_csv(VALDIR / "summary.csv")
        s = s[(s.variable == "income_median_bias_pct") & s.year.between(2021, 2023)].copy()
        s["absv"] = s.tv.abs()
        for st, g in s.groupby("state"):
            med_bias[st] = g.loc[g.absv.idxmax(), "tv"]
    except Exception:
        pass
    inc_col = list(fc.columns).index("hh_inc9") if "hh_inc9" in fc.columns else None
    fig, ax = plt.subplots(figsize=(min(trb_style.COL2, 0.75 * M.shape[1] + 2.2),
                                    0.6 * M.shape[0] + 1.6))
    # Sequential perceptually-uniform, colour-blind-safe map (paper-wide spec):
    # darker (lower viridis) = smaller gap, brighter = larger gap. The 5 pp
    # acceptance threshold is marked as a neutral line on the colour bar.
    vmax = max(TOL * 2, np.nanmax(M))
    norm = Normalize(vmin=0, vmax=vmax)
    cmap = plt.get_cmap(trb_style.SEQ_CMAP)
    im = ax.imshow(M, cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(M.shape[1])); ax.set_xticklabels([VLAB.get(c, c) for c in fc.columns])
    ax.set_yticks(range(M.shape[0])); ax.set_yticklabels(fc.index)
    ax.grid(False)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if np.isfinite(v):
                r, g, b, _ = cmap(norm(v))          # cell colour -> luminance
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                txt = "black" if lum > 0.55 else "white"
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=8, color=txt)
                # overlay the median-income bias inside the HH-income cells
                if j == inc_col:
                    mb = med_bias.get(fc.index[i])
                    if mb is not None:
                        ax.text(j, i + 0.30, f"med {mb:+.1f}%", ha="center", va="center",
                                fontsize=6.2, style="italic", color=txt)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02); cb.set_label("max per-bin gap (pp)")
    cb.ax.axhline(TOL, color=trb_style.NEUTRAL, linewidth=1.2)
    cap = (f"Figure 1. SILO vs. ACS worst per-bin gap (percentage points) by state and "
           f"attribute over the out-of-sample forecast window 2021–2023 (scenario {SCEN}); "
           f"brighter = larger gap, with the {TOL:.0f} pp acceptance threshold marked on the "
           f"colour bar. HH-income cells also print "
           f"the worst-magnitude median-income bias (“med ±%”): a green per-bin gap "
           f"can coexist with a materially biased median dollar income. Coverage is 6 states "
           f"through 2022; 2023 ACS PUMS is MD/DE/DC only (VA/PA/WV end 2022).")
    return _save_both(fig, "scorecard_heatmap", cap)


def trajectory(df):
    # Plot the worst per-bin gap PER STATE (max across all attributes) — one line
    # per state. Averaging across states (the old behaviour) hid single-state
    # failures (DC age, WV autos/dwelling) and faked a 2023 dip caused purely by
    # the state set shrinking 6->3 that year, not by improved fit (TRB audit M3).
    fig, ax = plt.subplots(figsize=trb_style.size(trb_style.COL2, 0.55))
    statelist = [s for s in STATES if s in df.state.unique()]
    for k, st in enumerate(statelist):
        s = df[df.state == st].groupby("year").max_bin_pp.max()
        ax.plot(s.index, s.values, marker=trb_style.MARKERS[k % len(trb_style.MARKERS)],
                ls=trb_style.LINESTYLES[k % len(trb_style.LINESTYLES)],
                color=trb_style.STATE_COLORS.get(st, trb_style.PALETTE[k % len(trb_style.PALETTE)]),
                label=st)
    ax.axhspan(0, TOL, color=trb_style.NEUTRAL, alpha=0.07)
    ax.axhline(TOL, color=trb_style.NEUTRAL, ls="--", lw=1.0, label=f"{TOL:.0f} pp acceptance")
    ax.axvspan(2020.5, 2023.5, color=trb_style.NEUTRAL, alpha=0.06)
    ax.text(2022, ax.get_ylim()[1] * 0.96, "forecast", ha="center", fontsize=8, color=trb_style.NEUTRAL)
    # disclose that the state set shrinks at 2023 (VA/PA/WV have no 2023 ACS PUMS)
    sy = _states_by_year(df)
    if 2023 in sy and len(sy[2023]) < len(statelist):
        ax.axvline(2022.5, color=trb_style.NEUTRAL, ls=":", lw=0.8)
        ax.text(2022.55, ax.get_ylim()[1] * 0.80,
                "2023: " + "/".join(sy[2023]) + " only", ha="left", va="top",
                fontsize=6.8, color=trb_style.NEUTRAL, rotation=90)
    ax.set_xlabel("Year"); ax.set_ylabel("Worst per-bin gap across attributes (pp)")
    ax.grid(True, axis="y"); ax.legend(ncol=2, loc="upper left")
    covered = " ".join(f"{y}:{len(v)}st" for y, v in sorted(sy.items()) if len(v) < len(statelist)) or "all years 6-state"
    cap = (f"Figure 2. Worst per-bin gap per state (max over all attributes) by year, "
           f"2016–2023, scenario {SCEN}; shaded region marks the out-of-sample "
           f"forecast window and the {TOL:.0f} pp acceptance band. Lines are per state, "
           f"NOT a cross-state mean, so single-state failures stay visible. State "
           f"coverage is 6 states through 2022; 2023 ACS PUMS covers "
           f"{'/'.join(sy.get(2023, []))} only ({covered}).")
    return _save_both(fig, "error_trajectory", cap)


def main():
    FIGDIR.mkdir(parents=True, exist_ok=True)
    ORIGDIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(VALDIR / "perbin_scorecard.csv")
    for pair in (heatmap(df), trajectory(df)):
        print("wrote", *pair)


if __name__ == "__main__":
    main()
