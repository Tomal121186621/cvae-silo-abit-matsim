"""Constants, local input paths, PUMS recode maps, income bin edges, cardinalities.

Everything downstream imports from here. Paths resolve relative to this file so the
project is self-contained (inputs were copied into ./inputs).

Design notes vs the old vae_silo_v6:
  - Income is BINNED (categorical) — there is NO income top-code clip and NO Pareto/tail
    threshold here. The open top bin (edge = +inf) keeps the genuine $1M+ values; continuous
    dollars are recovered at generation by an empirical within-(PUMA, bin) draw.
  - Bin edges below are sensible DEFAULTS; `steps/00_analyze_raw_acs.py` writes data-driven
    edges to outputs/00_raw_analysis/income_bin_edges.json, which `load_income_bin_edges()`
    picks up if present (the "analyze before preprocessing" gate).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Final

# ── Paths (self-contained) ───────────────────────────────────────────────
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent  # Updated VAE/
INPUTS_DIR: Final[Path] = PROJECT_ROOT / "inputs"
OUTPUTS_DIR: Final[Path] = PROJECT_ROOT / "outputs"

PUMS_DIR: Final[Path] = INPUTS_DIR / "pums"
ZONE_SYSTEM_CSV: Final[Path] = INPUTS_DIR / "zoneSystem.csv"
COVERAGE_JSON: Final[Path] = INPUTS_DIR / "coverage_fractions.json"
ACTIVITIES_CSV: Final[Path] = INPUTS_DIR / "Activities_2016.csv"
TLFD_CSV: Final[Path] = INPUTS_DIR / "hts_work_TLFD.csv"
FORECAST_CSV: Final[Path] = INPUTS_DIR / "employmentForecast_ron_orig.csv"
SKIM_OMX: Final[Path] = INPUTS_DIR / "skims" / "HwyPK_iter6.omx"

# ── Region / base year ───────────────────────────────────────────────────
BASE_YEAR: Final[int] = 2016
MSTM_STATE_FIPS: Final[tuple[int, ...]] = (10, 11, 24, 42, 51, 54)
STATE_FIPS_ABBREV: Final[dict[int, str]] = {
    10: "DE", 11: "DC", 24: "MD", 42: "PA", 51: "VA", 54: "WV",
}
# VA independent cities folded upward into parent counties at PUMA aggregation.
VA_INDEPENDENT_CITIES: Final[dict[int, int]] = {
    51600: 51059, 51610: 51059, 51683: 51153, 51685: 51153,
}

# ── ACS PUMS columns read ────────────────────────────────────────────────
HH_COLS_NEEDED: Final[tuple[str, ...]] = (
    "SERIALNO", "PUMA", "WGTP", "NP", "VEH", "HINCP", "ADJINC",
    "BLD", "YBL", "BDSP", "GRNTP", "SMOCP", "TEN", "TYPE",
)
PP_COLS_NEEDED: Final[tuple[str, ...]] = (
    "SERIALNO", "SPORDER", "PWGTP", "AGEP", "SEX", "RAC1P", "HISP",
    "ESR", "SCHG", "PINCP", "ADJINC", "NATIVITY", "CIT", "RELP",
    "POWPUMA", "POWSP", "JWTR", "JWTRNS",   # JWTR (≤2018) / JWTRNS (≥2019), coalesced
)

# ── Recode maps (ACS 5-yr 2016 schema) ───────────────────────────────────
VEH_MAP: Final[dict[int, int]] = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 4, 6: 4}
# ACS BLD → SILO dwellingType: 1=SFD, 2=SFA, 3=MF2-4, 4=MF5+, 5=MH/Other.
BLD_TO_TYPE: Final[dict[int, int]] = {
    1: 5, 2: 1, 3: 2, 4: 3, 5: 3, 6: 4, 7: 4, 8: 4, 9: 4, 10: 5,
}
# ACS 2012-2016 YBL codes (verified vs PUMS_Data_Dictionary_2012-2016.pdf): codes 1-7 are
# decade bins, 8 = 2000-2004, and 9-20 are INDIVIDUAL years 2005..2016. (The previous map
# used the obsolete pre-2012 ordinal scheme and was wrong — codes misaligned + 17-20 missing.)
YBL_TO_YEAR: Final[dict[int, int]] = {
    1: 1935, 2: 1945, 3: 1955, 4: 1965, 5: 1975, 6: 1985, 7: 1995,
    8: 2002, 9: 2005, 10: 2006, 11: 2007, 12: 2008, 13: 2009, 14: 2010,
    15: 2011, 16: 2012, 17: 2013, 18: 2014, 19: 2015, 20: 2016,
}
# ACS 2012-2016 RELP (0..17) → SILO relationship (0..7). Verified vs dictionary:
# 0=ref→head, 1=spouse, 2/3/4=child(bio/adopt/step), 5=sibling, 6=parent,
# 7/8/9/10=other-relative, 11=roomer, 12/13/14/15=other-nonrel, 16/17=GQ.
RELP_MAP: Final[dict[int, int]] = {
    0: 0, 1: 1, 2: 2, 3: 2, 4: 2, 5: 3, 6: 4, 7: 5, 8: 5,
    9: 5, 10: 5, 11: 6, 12: 7, 13: 7, 14: 7, 15: 7, 16: 7, 17: 7,
}

# ── Income binning (DEFAULTS; step 00 may override via JSON) ──────────────
# No top-code clip. Last edge = +inf → open top bin keeps the genuine high incomes.
_INF: Final[float] = math.inf
# Household income: fine in the body, coarser through the long tail (incl. negatives).
HH_INCOME_BIN_EDGES_DEFAULT: Final[tuple[float, ...]] = (
    -_INF, 0, 10_000, 15_000, 20_000, 25_000, 30_000, 40_000, 50_000,
    60_000, 75_000, 100_000, 125_000, 150_000, 175_000, 200_000,
    250_000, 300_000, 400_000, 500_000, 750_000, 1_000_000, _INF,
)
# Person income: bin 0 = non-earner (income <= 0); positive bins start at >0.
# (second edge = 1 so income==0/negatives fall cleanly into the dedicated bin 0.)
PP_INCOME_BIN_EDGES_DEFAULT: Final[tuple[float, ...]] = (
    -_INF, 1, 10_000, 20_000, 30_000, 40_000, 50_000, 65_000, 80_000,
    100_000, 125_000, 150_000, 200_000, 300_000, 500_000, 1_000_000, _INF,
)


def _edges_path() -> Path:
    return OUTPUTS_DIR / "00_raw_analysis" / "income_bin_edges.json"


def load_income_bin_edges() -> tuple[list[float], list[float]]:
    """Return (hh_edges, pp_edges). Prefer the data-driven edges written by step 00;
    fall back to the defaults above. inf is stored as null in JSON and restored here."""
    p = _edges_path()
    if p.exists():
        d = json.loads(p.read_text())
        fix = lambda xs: [(-_INF if v is None and i == 0 else _INF if v is None else float(v))
                          for i, v in enumerate(xs)]
        return fix(d["hh"]), fix(d["pp"])
    return list(HH_INCOME_BIN_EDGES_DEFAULT), list(PP_INCOME_BIN_EDGES_DEFAULT)


def save_income_bin_edges(hh_edges, pp_edges) -> Path:
    """Persist chosen edges (inf → null) for downstream steps."""
    p = _edges_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    enc = lambda xs: [None if (v == _INF or v == -_INF) else float(v) for v in xs]
    p.write_text(json.dumps({"hh": enc(list(hh_edges)), "pp": enc(list(pp_edges))}, indent=2))
    return p


# ── Category cardinalities ───────────────────────────────────────────────
N_DWELLING_TYPES: Final[int] = 5
N_TENURE: Final[int] = 2
N_AUTOS: Final[int] = 5            # 0..4
N_HH_SIZES: Final[int] = 7         # clipped 1..7 (S_MAX)
S_MAX: Final[int] = 7              # max persons per household modeled

N_AGE_BINS: Final[int] = 18        # 5-yr bins 0..85+
N_GENDER: Final[int] = 2           # 1=male, 2=female
N_RACE: Final[int] = 5             # White/Black/Hisp/Asian/Other (NH)
N_OCCUPATION: Final[int] = 6
N_LICENSE: Final[int] = 2          # 0=no, 1=yes
N_RELATIONSHIP: Final[int] = 8     # internal RELP codes 0..7
N_NATIONALITY: Final[int] = 3      # 1=native, 2=naturalized, 3=non-citizen


def puma_key(state_fips, puma_5) -> str:
    """Canonical PUMA id: '{state_fips}_{puma:05d}'."""
    return f"{int(state_fips)}_{str(puma_5).strip().zfill(5)}"


def n_hh_income_bins() -> int:
    return len(load_income_bin_edges()[0]) - 1


def n_pp_income_bins() -> int:
    return len(load_income_bin_edges()[1]) - 1
