#!/usr/bin/env python3
"""STEP 00 (runs BEFORE preprocessing) — statistical analysis + visualization of every
raw ACS PUMS 2016 source variable the VAE uses, plus income tail diagnostics, the age
lifecycle, and an income-bin occupancy report that finalizes the bin edges.

Outputs → outputs/00_raw_analysis/ :
  raw_descriptive_stats.csv, raw_housing_stats.png, raw_person_stats.png,
  income_tail_diagnostics.png, age_lifecycle.png, income_bin_occupancy.png,
  income_bin_edges.json
This is a review GATE: eyeball the stats/visuals before running step 01.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Updated VAE/

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from vaelib import config, analysis as A
from vaelib.pums_io import load_all_states_raw

OUT = config.OUTPUTS_DIR / "00_raw_analysis"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"figure.dpi": 110, "font.size": 8, "axes.grid": True,
                     "grid.alpha": .3, "axes.axisbelow": True})

# ── load raw ACS ─────────────────────────────────────────────────────────
print("Loading raw ACS PUMS 2016 (6 states)...", flush=True)
H, P = load_all_states_raw(config.HH_COLS_NEEDED, config.PP_COLS_NEEDED)
n = lambda df, c: pd.to_numeric(df[c], errors="coerce")
H = H[n(H, "TYPE") == 1].copy()                     # occupied housing units for HH attrs
H["w"] = n(H, "WGTP"); P["w"] = n(P, "PWGTP")
H["inc"] = n(H, "HINCP") * n(H, "ADJINC") / 1e6     # ADJINC-adjusted 2016 $
P["inc"] = n(P, "PINCP") * n(P, "ADJINC") / 1e6
print(f"HH(occupied)={len(H):,}  PP={len(P):,}\n", flush=True)

# ── per-variable descriptive stats → CSV ─────────────────────────────────
rows, cat_pcts = [], {}
CONT = {"household": [("NP", "NP"), ("BDSP", "BDSP"), ("GRNTP", "GRNTP"),
                      ("SMOCP", "SMOCP"), ("inc", "HINCP_adj"), ("w", "WGTP")],
        "person":    [("AGEP", "AGEP"), ("inc", "PINCP_adj"), ("w", "PWGTP")]}
CAT = {"household": ["VEH", "BLD", "TEN", "YBL"],
       "person":    ["SEX", "RAC1P", "HISP", "ESR", "RELP", "JWTR", "NATIVITY", "CIT"]}
for level, df in (("household", H), ("person", P)):
    for col, name in CONT[level]:
        s = A.continuous_stats(df[col], df["w"]); s.update(level=level, var=name); rows.append(s)
    for col in CAT[level]:
        summ, pct = A.categorical_stats(df[col], df["w"]); summ.update(level=level, var=col)
        rows.append(summ); cat_pcts[(level, col)] = pct
pd.DataFrame(rows).to_csv(OUT / "raw_descriptive_stats.csv", index=False)
print(f"saved {OUT/'raw_descriptive_stats.csv'}")

# ── visualization helpers ────────────────────────────────────────────────
def ahist(ax, df, col, title, bins, clip=None, dz=False):
    x = n(df, col).to_numpy(float); w = df["w"].to_numpy(float); m = ~np.isnan(x)
    if dz: m &= x > 0
    x, w = x[m], w[m]; mu = A.wmean(x, w); med = A.wquantile(x, w, .5)
    ax.hist(np.clip(x, *clip) if clip else x, bins=bins, weights=w,
            color="#55A868", edgecolor="white")
    ax.axvline(med if not clip else min(med, clip[1]), color="red", ls="--", lw=1)
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.text(.97, .95, f"mean={mu:,.0f}\nmed={med:,.0f}\nskew={A.wmoment(x,w,3):.1f}",
            transform=ax.transAxes, ha="right", va="top", fontsize=6.5,
            bbox=dict(boxstyle="round", fc="white", alpha=.7))

def abar(ax, level, col, title, labs=None, topn=None):
    pct = cat_pcts[(level, col)]
    if topn: pct = pct.iloc[:topn]
    ax.bar(range(len(pct)), pct.values, color="#4C72B0", edgecolor="white")
    ax.set_xticks(range(len(pct)))
    ax.set_xticklabels(labs if labs else [int(i) for i in pct.index],
                       rotation=45 if (labs and len(labs) > 4) or len(pct) > 10 else 0, fontsize=6.5)
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.text(.97, .95, f"mode={int(pct.idxmax())}\n{pct.max():.0f}%", transform=ax.transAxes,
            ha="right", va="top", fontsize=6.5, bbox=dict(boxstyle="round", fc="white", alpha=.7))

# ── housing grid ─────────────────────────────────────────────────────────
fig, ax = plt.subplots(3, 3, figsize=(16, 12)); a = ax.ravel()
ahist(a[0], H, "NP", "NP persons/HH (→hhSize)", range(0, 13))
ahist(a[1], H, "BDSP", "BDSP bedrooms (→bedrooms)", range(0, 12))
ahist(a[2], H, "inc", "HINCP×ADJINC (→income_bin) $0-400k", 50, clip=(0, 400_000), dz=True)
ahist(a[3], H, "GRNTP", "GRNTP gross rent ($/mo)", 40, dz=True)
ahist(a[4], H, "SMOCP", "SMOCP owner cost ($/mo)", 40, dz=True)
abar(a[5], "household", "VEH", "VEH vehicles (→autos)")
abar(a[6], "household", "BLD", "BLD building (→dwellingType)", topn=10)
abar(a[7], "household", "TEN", "TEN tenure (→tenure)", ["own", "mortg", "rent", "nocash"])
abar(a[8], "household", "YBL", "YBL year built (→yearBuilt)")
fig.suptitle("RAW ACS 2016 — HOUSING source variables (weighted; red dash=median)",
             fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.96]); fig.savefig(OUT / "raw_housing_stats.png"); plt.close(fig)

# ── person grid ──────────────────────────────────────────────────────────
fig, ax = plt.subplots(3, 3, figsize=(16, 12)); a = ax.ravel()
ahist(a[0], P, "AGEP", "AGEP age (→age_bin)", range(0, 101, 2))
ahist(a[1], P, "inc", "PINCP×ADJINC (→income_bin) $0-250k", 50, clip=(0, 250_000), dz=True)
abar(a[2], "person", "SEX", "SEX (→gender)", ["male", "female"])
abar(a[3], "person", "RAC1P", "RAC1P (→race w/ HISP)")
abar(a[4], "person", "HISP", "HISP origin (→race)", topn=8)
abar(a[5], "person", "ESR", "ESR employment (→occupation)")
abar(a[6], "person", "RELP", "RELP (→relationship)", topn=18)
abar(a[7], "person", "JWTR", "JWTR commute (→driversLicense)")
abar(a[8], "person", "CIT", "CIT citizenship (→nationality)")
fig.suptitle("RAW ACS 2016 — PERSON source variables (weighted; red dash=median)",
             fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.96]); fig.savefig(OUT / "raw_person_stats.png"); plt.close(fig)

# ── income tail diagnostics ──────────────────────────────────────────────
inc = H.loc[H["inc"].notna(), "inc"].to_numpy(); w = H.loc[H["inc"].notna(), "w"].to_numpy()
incp = inc[inc > 0]
print("\nHH income tail (Hill alpha):")
for u in [100_000, 200_000, 300_000, 500_000, 1_000_000]:
    al, ne = A.hill_alpha(incp, w, u)
    print(f"  u=${u:>9,}: Hill alpha={al:5.2f}  n_exceed={ne:>6,}  share={(incp>u).mean()*100:5.2f}%")
fig, ax = plt.subplots(1, 3, figsize=(18, 5))
s = np.sort(incp); ccdf = 1 - np.arange(len(s)) / len(s)
ax[0].loglog(s, ccdf, ".", ms=1, color="#333", alpha=.4)
ax[0].axvline(300_000, color="red", ls=":"); ax[0].axvline(1e6, color="purple", ls=":")
ax[0].set_title("Log-log survival (straight ⇒ Pareto)", fontweight="bold")
ax[0].set_xlabel("income $"); ax[0].set_ylabel("P(>x)")
us = np.geomspace(50_000, 1_000_000, 40)
ax[1].semilogx(us, [A.hill_alpha(incp, w, u)[0] for u in us], "-o", ms=3, color="#C44E52")
ax[1].axhline(2.0, color="gray", ls="--", label="Gabaix α=2"); ax[1].axvline(300_000, color="red", ls=":")
ax[1].set_title("Hill plot (flat ⇒ Pareto holds)", fontweight="bold")
ax[1].set_xlabel("threshold u"); ax[1].set_ylabel("Hill α"); ax[1].legend(fontsize=7)
us2 = np.linspace(50_000, 800_000, 60)
me = [(incp[incp > u] - u).mean() if (incp > u).sum() > 20 else np.nan for u in us2]
ax[2].plot(us2 / 1000, np.array(me) / 1000, color="#4C72B0"); ax[2].axvline(300, color="red", ls="--")
ax[2].set_title("Mean-excess (rising ⇒ heavy tail)", fontweight="bold")
ax[2].set_xlabel("threshold u ($k)"); ax[2].set_ylabel("mean excess ($k)")
fig.suptitle("RAW ACS 2016 — HH income tail diagnostics", fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.95]); fig.savefig(OUT / "income_tail_diagnostics.png"); plt.close(fig)

# ── age lifecycle ────────────────────────────────────────────────────────
pp = P[P["AGEP"].notna()].copy(); pp["age"] = n(pp, "AGEP"); pp["sex"] = n(pp, "SEX")
fig, ax = plt.subplots(1, 3, figsize=(18, 5))
bins = np.arange(0, 101, 5)
for sx, c, lab, sgn in [(1, "#4C72B0", "male", -1), (2, "#C44E52", "female", 1)]:
    m = pp["sex"] == sx
    cnt, _ = np.histogram(pp.loc[m, "age"], bins=bins, weights=pp.loc[m, "w"])
    ax[0].barh(bins[:-1] + 2.5, sgn * cnt, height=4, color=c, label=lab)
ax[0].set_title("Age pyramid (weighted)", fontweight="bold"); ax[0].set_ylabel("age"); ax[0].legend()
ageg = pp[(pp["age"] >= 15) & pp["inc"].notna()].copy(); ageg["ab"] = (ageg["age"] // 5 * 5).clip(15, 85)
g = ageg.groupby("ab").apply(lambda d: pd.Series({
    "median": np.median(d["inc"][d["inc"] > 0]) if (d["inc"] > 0).any() else 0,
    "earner": (d["inc"] > 0).mean() * 100}), include_groups=False)
ax[1].plot(g.index, g["median"] / 1000, "-o", color="#4C72B0")
ax[1].set_title("Median earner income by age", fontweight="bold")
ax[1].set_xlabel("age"); ax[1].set_ylabel("income ($k)")
ax[2].plot(g.index, g["earner"], "-o", color="#8172B3")
ax[2].set_title("Share with positive income by age", fontweight="bold")
ax[2].set_xlabel("age"); ax[2].set_ylabel("% earners")
fig.suptitle("RAW ACS 2016 — age structure & age-income lifecycle", fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.95]); fig.savefig(OUT / "age_lifecycle.png"); plt.close(fig)

# ── income bin occupancy + finalize edges ────────────────────────────────
hh_edges, pp_edges = config.HH_INCOME_BIN_EDGES_DEFAULT, config.PP_INCOME_BIN_EDGES_DEFAULT
hh_occ = A.income_bin_occupancy(H["inc"], H["w"], hh_edges)
pp_occ = A.income_bin_occupancy(P["inc"], P["w"], pp_edges)
print("\nWeighted income quantiles (HH): " +
      ", ".join(f"P{int(q*100)}=${A.wquantile(incp, w, q):,.0f}" for q in (.5, .9, .95, .99)))
print(f"HH income-bin occupancy (%): {np.round(hh_occ, 2).tolist()}")
print(f"PP income-bin occupancy (%): {np.round(pp_occ, 2).tolist()}")
fig, ax = plt.subplots(1, 2, figsize=(16, 5))
ax[0].bar(range(len(hh_occ)), hh_occ, color="#4C72B0"); ax[0].set_title(
    f"HH income-bin occupancy ({len(hh_occ)} bins; last=open tail)", fontweight="bold")
ax[0].set_xlabel("bin index"); ax[0].set_ylabel("% weighted")
ax[1].bar(range(len(pp_occ)), pp_occ, color="#55A868"); ax[1].set_title(
    f"PP income-bin occupancy ({len(pp_occ)} bins; bin0=non-earner, last=open tail)", fontweight="bold")
ax[1].set_xlabel("bin index"); ax[1].set_ylabel("% weighted")
fig.tight_layout(); fig.savefig(OUT / "income_bin_occupancy.png"); plt.close(fig)
saved = config.save_income_bin_edges(hh_edges, pp_edges)
print(f"\nsaved income bin edges → {saved}")
print(f"all step-00 outputs → {OUT}")
for p in sorted(OUT.glob("*")): print("  ", p.name)
print("\nDONE — review the stats/visuals before running step 01.")
