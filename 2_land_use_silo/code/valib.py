#!/usr/bin/env python3
"""Self-contained validation library for the SILO stage (rebuilt after the scripts/ deletion).

Provides everything validate_allstates.py needs:
  - PUMS reading (read_pums_zip) + per-year PUMS directory (pums_dir) + CPI deflators
  - recode maps/cuts (BLD_TO_TYPE, HH_INC_CUTS) and weighted quantile (wq)
  - SILO per-year loader (load_silo_year) recoding SILO output to the validation schema
  - variable lists (HH_VARS, PP_VARS) and one_var_fig (weighted TV + comparison figure)

SILO output schema (no race column -> race4 is not validated from output):
  hh: id,dwelling,hhSize,autos      dd: id,zone,type,...     pp: id,hhid,age,gender,
  relationShip,occupation,driversLicense,workplace,income
Household income is summed from person incomes; state comes via hh->dwelling->zone->STFIPS.
"""
from __future__ import annotations
import io, zipfile, os
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys as _sys
_sys.path.insert(0, "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/code")
import trb_style  # shared TRB/TRR figure style

DEL = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM")
INPUTS = DEL / "inputs"
ZONESYS = Path("/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test/input/zoneSystem.csv")

# SILO scenario microData dir (validate_allstates.py overrides this via valib.SCEN = ...)
SCEN = Path("/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test/scenOutput/updated_vae_fcast/microData")

STATES6 = {10: "DE", 11: "DC", 24: "MD", 42: "PA", 51: "VA", 54: "WV"}

# ACS BLD -> dwellingType (1..5); SILO dwelling type names -> same 1..5 scheme
BLD_TO_TYPE = {1: 5, 2: 1, 3: 2, 4: 3, 5: 3, 6: 4, 7: 4, 8: 4, 9: 4, 10: 5}
SILO_TYPE_TO_INT = {"SFD": 1, "SFA": 2, "MF234": 3, "MF5plus": 4, "MH": 5}

# 9-group household income classification (same cuts applied to SILO and ACS -> comparable TV)
HH_INC_CUTS = [-np.inf, 15000, 30000, 45000, 60000, 75000, 100000, 125000, 150000, np.inf]

# CPI-U annual average (US city average); deflate each year's $ to 2016$ via CPI[2016]/CPI[year]
CPI = {2016: 240.007, 2017: 245.120, 2018: 251.107, 2019: 255.657, 2020: 258.811,
       2021: 270.970, 2022: 292.655, 2023: 304.702, 2024: 313.689}

# variables validated (var, title). race4 is included when the SILO output carries a race column
# (PersonWriterMstm); validate_allstates skips it for older output that lacks the column.
HH_VARS = [("hhSize", "Household size"), ("autos", "Autos per household"),
           ("dwellingType", "Dwelling type"), ("hh_inc9", "Household income group")]
PP_VARS = [("age_bin", "Age (5-yr bins)"), ("gender", "Gender"), ("occ_silo", "Occupation"),
           ("race4", "Race/ethnicity")]

_COL = dict(trb_style.STATE_COLORS)   # paper-wide fixed per-state colours


def pums_dir(year: int) -> Path:
    return INPUTS / "pums" if year == 2016 else INPUTS / f"pums_{year}_5yr"


def read_pums_zip(path: Path, cols: list[str]) -> pd.DataFrame:
    """Read the single CSV inside a PUMS zip, keeping only the requested columns that exist."""
    with zipfile.ZipFile(path) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        with z.open(name) as f:
            head = pd.read_csv(io.BytesIO(f.read(4096)), nrows=0)
        keep = [c for c in cols if c in head.columns]
        with z.open(name) as f:
            return pd.read_csv(f, usecols=keep, dtype=str, low_memory=False)


def wq(values: np.ndarray, weights: np.ndarray, qs) -> np.ndarray:
    """Weighted quantile(s)."""
    v = np.asarray(values, float); w = np.asarray(weights, float)
    m = np.isfinite(v) & (w > 0); v, w = v[m], w[m]
    if len(v) == 0:
        return np.array([np.nan for _ in qs])
    o = np.argsort(v); v, w = v[o], w[o]
    cw = np.cumsum(w) - 0.5 * w; cw /= w.sum()
    return np.interp(qs, cw, v)


def _zone_to_state() -> dict[int, int]:
    z = pd.read_csv(ZONESYS, usecols=["ZoneId", "STFIPS"])
    return dict(zip(z.ZoneId.astype(int), z.STFIPS.astype(int)))


def load_silo_year(year: int):
    """Load SILO hh/pp for a year, recoded to the validation schema with a `state` label."""
    z2s = _zone_to_state()
    dd = pd.read_csv(SCEN / f"dd_{year}.csv", usecols=["id", "zone", "type"])
    dd["state"] = dd.zone.map(z2s)
    dd["dwellingType"] = dd.type.astype(str).str.strip().str.strip('"').map(SILO_TYPE_TO_INT).fillna(1).astype(int)

    pp = pd.read_csv(SCEN / f"pp_{year}.csv", usecols=["hhid", "age", "gender", "occupation", "income"])
    pp["income"] = pd.to_numeric(pp.income, errors="coerce").fillna(0.0)
    hh_income = pp.groupby("hhid").income.sum()

    hh = pd.read_csv(SCEN / f"hh_{year}.csv", usecols=["id", "dwelling", "hhSize", "autos"])
    ddx = dd.set_index("id")
    hh["state"] = hh.dwelling.map(ddx.state)
    hh["dwellingType"] = hh.dwelling.map(ddx.dwellingType).fillna(1).astype(int)
    hh["hhSize"] = pd.to_numeric(hh.hhSize, errors="coerce").clip(1, 7).astype(int)
    hh["autos"] = pd.to_numeric(hh.autos, errors="coerce").fillna(0).clip(0, 3).astype(int)
    hh["income"] = hh.id.map(hh_income).fillna(0.0)
    hh["hh_inc9"] = pd.cut(hh.income.astype(float), HH_INC_CUTS, labels=False, right=True).astype("Int64").fillna(0).astype(int)
    hh["state"] = hh.state.map(STATES6)                 # FIPS -> abbrev
    hh["w"] = 1.0

    # persons: attach state via their household; recode
    hh_state = hh.set_index("id").state
    ppcols = pd.read_csv(SCEN / f"pp_{year}.csv", nrows=0).columns
    want = [c for c in ["hhid", "age", "gender", "occupation", "race"] if c in ppcols]
    pp2 = pd.read_csv(SCEN / f"pp_{year}.csv", usecols=want)
    pp2["state"] = pp2.hhid.map(hh_state)
    pp2["age"] = pd.to_numeric(pp2.age, errors="coerce").clip(0, 99).fillna(0).astype(int)
    pp2["age_bin"] = (pp2.age // 5).clip(0, 17).astype(int)
    pp2["gender"] = pd.to_numeric(pp2.gender, errors="coerce").clip(1, 2).fillna(1).astype(int)
    pp2["occ_silo"] = pd.to_numeric(pp2.occupation, errors="coerce").clip(0, 4).fillna(2).astype(int)
    if "race" in pp2.columns:                          # SILO Race enum -> white/black/hispanic/other
        pp2["race4"] = pp2.race.astype(str).str.strip().str.strip('"').str.lower()
    pp2["w"] = 1.0
    return hh, pp2


def _wdist(vals, w, cats):
    idx = {c: i for i, c in enumerate(cats)}; h = np.zeros(len(cats))
    v = np.asarray(vals); w = np.asarray(w, float)
    for val, wt in zip(v, w):
        j = idx.get(val)
        if j is not None:
            h[j] += wt
    s = h.sum()
    return h / s if s > 0 else h


# Ordered categories + human-readable tick labels per variable, so figures are publication-ready
# (no raw integer codes). Keys match the `var` passed to one_var_fig.
VAR_CATEGORIES = {
    "hhSize":       (list(range(1, 8)),  ["1", "2", "3", "4", "5", "6", "7+"]),
    "autos":        (list(range(0, 4)),  ["0", "1", "2", "3+"]),
    "dwellingType": (list(range(1, 6)),  ["SF detached", "SF attached", "MF 2–4", "MF 5+", "Mobile"]),
    "hh_inc9":      (list(range(0, 9)),  ["<15k", "15–30k", "30–45k", "45–60k", "60–75k",
                                          "75–100k", "100–125k", "125–150k", "150k+"]),
    "age_bin":      (list(range(0, 18)), [f"{5*i}–{5*i+4}" for i in range(17)] + ["85+"]),
    "gender":       ([1, 2],             ["Male", "Female"]),
    "occ_silo":     (list(range(0, 5)),  ["Child", "Employed", "Unemployed", "Student", "Retiree"]),
    "race4":        (["white", "black", "hispanic", "other"], ["White", "Black", "Hispanic", "Other"]),
}

# Consistent publication palette (shared TRB/TRR style; grayscale-legible)
_ACS_COLOR = trb_style.OBS      # observed / ground truth (vermillion)
_SILO_COLOR = trb_style.SIM     # model (blue)
_OK_COLOR = trb_style.TARGET    # within tolerance (green)
_BAD_COLOR = trb_style.OBS      # exceeds 5pp band (vermillion)


def one_var_fig(path: Path, var, title, year, svals, sw, rvals, rw, tol_pp: float = 5.0,
                caption_text: str | None = None) -> float:
    """Publication-quality SILO-vs-ACS comparison for one variable: a grouped share bar chart plus a
    signed per-bin difference panel with the ±tol_pp acceptance band. Returns the Total Variation."""
    if var in VAR_CATEGORIES:
        cats, labels = VAR_CATEGORIES[var]
    else:
        cats = sorted(set(pd.unique(svals)).union(set(pd.unique(rvals))), key=lambda x: (str(type(x)), x))
        labels = [str(c) for c in cats]
    sp = _wdist(svals, sw, cats); rp = _wdist(rvals, rw, cats)
    tv = 0.5 * float(np.abs(sp - rp).sum())
    diff_pp = (sp - rp) * 100.0                      # SILO − ACS, percentage points
    maxbin = float(np.max(np.abs(diff_pp))) if len(diff_pp) else 0.0

    _w = min(trb_style.COL2, max(4.6, 0.52 * len(cats) + 2.4))
    fig, (ax, axd) = plt.subplots(2, 1, figsize=(_w, _w * 0.78),
                                  gridspec_kw={"height_ratios": [3, 1.6], "hspace": 0.30})
    x = np.arange(len(cats)); wbar = 0.42
    ax.bar(x - wbar/2, rp * 100, wbar, label="ACS (observed)", color=_ACS_COLOR, edgecolor="white", linewidth=0.5)
    ax.bar(x + wbar/2, sp * 100, wbar, label="SILO (model)", color=_SILO_COLOR, edgecolor="white", linewidth=0.5)
    ax.set_ylabel("Share of population (%)")
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.legend(loc="upper right")
    ax.margins(x=0.02); ax.grid(True, axis="y")

    # difference panel: green within ±tol, vermillion outside; neutral tolerance band
    bar_colors = [_BAD_COLOR if abs(d) > tol_pp else _OK_COLOR for d in diff_pp]
    axd.axhspan(-tol_pp, tol_pp, color=trb_style.NEUTRAL, alpha=0.08, zorder=0)
    axd.axhline(0, color="#333333", linewidth=0.9)
    axd.axhline(tol_pp, color=trb_style.NEUTRAL, linewidth=0.8, linestyle="--")
    axd.axhline(-tol_pp, color=trb_style.NEUTRAL, linewidth=0.8, linestyle="--")
    axd.bar(x, diff_pp, 0.6, color=bar_colors, edgecolor="white", linewidth=0.5)
    for xi, d in zip(x, diff_pp):
        if abs(d) >= 1.0:
            axd.annotate(f"{d:+.1f}", (xi, d), textcoords="offset points",
                         xytext=(0, 4 if d >= 0 else -11), ha="center", fontsize=7, color="#222222")
    lim = max(tol_pp + 1.5, 1.15 * maxbin)
    axd.set_ylim(-lim, lim)
    axd.set_ylabel("SILO − ACS (pp)")
    axd.set_xticks(x); axd.set_xticklabels(labels)
    axd.margins(x=0.02); axd.grid(True, axis="y")

    if caption_text is None:
        caption_text = (f"{title}, {year}: SILO vs. ACS PUMS shares (top) and signed "
                        f"per-bin gap with ±{tol_pp:.0f} pp band (bottom). "
                        f"Max per-bin gap = {maxbin:.1f} pp; TV = {tv:.3f}.")
    trb_style.save(fig, Path(path).with_suffix(""), caption_text=caption_text)
    return tv
