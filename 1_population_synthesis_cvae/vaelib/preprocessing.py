"""Recode raw ACS PUMS → SILO-schema frames for the simple CVAE.

Differences vs old vae_silo_v6:
  - Income is recoded to a BIN INDEX (HH + person) using config edges; the raw dollar value
    is kept alongside (`income_hh` / `income`) for the within-bin empirical sampler.
  - No income top-code clip, no tail flag, no Pareto machinery.
  - Person income for under-15 (null PINCP) → 0 → non-earner bin 0.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from . import config
from .income_bins import to_bin
from .pums_io import load_pums_zip

__all__ = ["recode_households", "recode_persons", "apply_coverage_scaling",
           "filter_to_mstm_pumas", "preprocess_state"]


def _int(s, default=0):
    return pd.to_numeric(s, errors="coerce").fillna(default).astype(int)


# ── households ───────────────────────────────────────────────────────────
def recode_households(raw: pd.DataFrame, state_fips: int) -> pd.DataFrame:
    if "TYPE" in raw.columns:
        raw = raw[_int(raw["TYPE"]) == 1].copy()        # housing units only
    out = pd.DataFrame(index=range(len(raw)))
    out["SERIALNO"] = raw["SERIALNO"].values
    puma_s = raw["PUMA"].astype(str).str.strip().str.zfill(5)
    out["PUMA"] = puma_s.values
    out["state_fips"] = int(state_fips)
    out["puma_key"] = (f"{int(state_fips)}_" + puma_s).values
    out["WGTP"] = _int(raw["WGTP"]).clip(0, 200).values

    np_s = _int(raw["NP"])
    out["hhSize"] = np_s.values                          # true size (uncapped)
    out["hhSizeVAE"] = np_s.clip(1, 7).values            # conditioning (S_MAX)

    out["autos"] = _int(raw.get("VEH", 0)).map(config.VEH_MAP).fillna(0).astype(int).clip(0, 4).values

    hincp = pd.to_numeric(raw.get("HINCP", 0), errors="coerce").fillna(0)
    adjinc = pd.to_numeric(raw.get("ADJINC", 1_000_000), errors="coerce").fillna(1_000_000)
    income = (hincp * adjinc / 1_000_000).round().astype(int)   # NO clip — open top bin
    out["income_hh"] = income.values
    hh_edges, _ = config.load_income_bin_edges()
    out["income_bin"] = to_bin(income.values, hh_edges)

    out["dwellingType"] = _int(raw.get("BLD", 2)).map(config.BLD_TO_TYPE).fillna(1).astype(int).values
    out["yearBuilt"] = _int(raw.get("YBL", 10)).map(config.YBL_TO_YEAR).fillna(1985).astype(int).values
    out["bedrooms"] = _int(raw.get("BDSP", 2)).clip(0, 5).values
    rent = pd.to_numeric(raw.get("GRNTP", 0), errors="coerce").fillna(0)
    own = pd.to_numeric(raw.get("SMOCP", 0), errors="coerce").fillna(0)
    out["monthlyCost"] = (rent + own).clip(0, 10_000).astype(int).values
    ten = _int(raw.get("TEN", 3))
    out["tenure"] = np.where(ten.values <= 2, 1, 2).astype(int)   # 1=own, 2=rent

    mask = (out["hhSize"] >= 1) & (out["hhSize"] <= 20)
    return out.loc[mask].reset_index(drop=True)


# ── persons ──────────────────────────────────────────────────────────────
def recode_persons(raw: pd.DataFrame, state_fips: int) -> pd.DataFrame:
    n = len(raw)
    out = pd.DataFrame(index=range(n))
    out["SERIALNO"] = raw["SERIALNO"].values
    out["state_fips"] = int(state_fips)
    out["SPORDER"] = _int(raw.get("SPORDER", 1)).values
    out["PWGTP"] = _int(raw["PWGTP"]).clip(0, 500).values

    age = _int(raw["AGEP"]).clip(0, 110)
    out["age"] = age.values
    out["age_bin"] = (age // 5).clip(0, 17).values

    out["gender"] = _int(raw["SEX"]).clip(1, 2).values

    rac = _int(raw["RAC1P"]).clip(1, 9).values
    hisp = _int(raw.get("HISP", 1)).clip(1, 24).values
    out["race"] = np.where(hisp > 1, 3, np.where(rac == 1, 1, np.where(rac == 2, 2,
                           np.where(np.isin(rac, [6, 7]), 4, 5)))).astype(int)

    esr = _int(raw.get("ESR", 6)).clip(0, 6).values
    schg = _int(raw.get("SCHG", 0)).clip(0, 15).values
    av = age.values
    out["occupation"] = np.where(av < 6, 5,                       # toddler
        np.where(np.isin(esr, [1, 2, 4, 5]), 1,                   # employed (incl armed forces)
        np.where(schg > 0, 2,                                     # student
        np.where(esr == 3, 4,                                     # unemployed
        np.where((av >= 62) & (esr == 6), 3, 6))))).astype(int)   # retiree / other

    # driver's license proxy from journey-to-work mode (JWTR ≤2018 / JWTRNS ≥2019)
    if "JWTRNS" in raw.columns:
        jw = _int(raw["JWTRNS"]).values
    elif "JWTR" in raw.columns:
        jw = _int(raw["JWTR"]).values
    else:
        raise KeyError("Neither JWTR nor JWTRNS in person file — cannot derive driversLicense.")
    no_car = np.isin(jw, [9, 10, 12])                             # bike/walk/other → unlicensed
    out["driversLicense"] = np.where(av < 16, 0, np.where(no_car, 0, 1)).astype(int)

    pincp = pd.to_numeric(raw.get("PINCP", 0), errors="coerce").fillna(0)  # null (under-15) → 0
    adjinc = pd.to_numeric(raw.get("ADJINC", 1_000_000), errors="coerce").fillna(1_000_000)
    income = (pincp * adjinc / 1_000_000).round().astype(int)
    out["income"] = income.values
    _, pp_edges = config.load_income_bin_edges()
    out["income_bin"] = to_bin(income.values, pp_edges)          # bin 0 = non-earner

    nat = _int(raw.get("NATIVITY", 1)).clip(1, 2).values
    cit = _int(raw.get("CIT", 1)).clip(1, 5).values
    out["nationality"] = np.where(nat == 1, 1, np.where(cit == 4, 2, 3)).astype(int)

    out["relationship"] = _int(raw.get("RELP", 0)).clip(0, 17).map(config.RELP_MAP).fillna(7).astype(int).values
    return out.reset_index(drop=True)


# ── coverage scaling & MSTM filter ───────────────────────────────────────
def apply_coverage_scaling(hh, pp, coverage_fractions):
    cov = hh["puma_key"].map(coverage_fractions).fillna(1.0).astype(float)
    hh = hh.copy()
    hh["WGTP_eff"] = (hh["WGTP"].astype(float) * cov).clip(lower=0.0)
    hh = hh[hh["WGTP_eff"] > 0].reset_index(drop=True)
    hh_idx = hh.set_index("SERIALNO")
    scale = hh_idx["WGTP_eff"].astype(float) / hh_idx["WGTP"].astype(float).clip(lower=1)
    pp = pp[pp["SERIALNO"].isin(hh_idx.index)].copy()
    pp["PWGTP_eff"] = (pp["PWGTP"].astype(float) * pp["SERIALNO"].map(scale).fillna(1.0)).clip(lower=0.0)
    pp = pp[pp["PWGTP_eff"] > 0].reset_index(drop=True)
    return hh, pp


def filter_to_mstm_pumas(hh, pp, mstm_pumas: Iterable[str]):
    mstm = set(mstm_pumas)
    hh = hh[hh["puma_key"].isin(mstm)].reset_index(drop=True)
    pp = pp[pp["SERIALNO"].isin(hh["SERIALNO"])].reset_index(drop=True)
    return hh, pp


def preprocess_state(state_fips, hh_zip, pp_zip, coverage_fractions, mstm_pumas):
    hh = recode_households(load_pums_zip(Path(hh_zip), config.HH_COLS_NEEDED), state_fips)
    pp = recode_persons(load_pums_zip(Path(pp_zip), config.PP_COLS_NEEDED), state_fips)
    hh, pp = filter_to_mstm_pumas(hh, pp, mstm_pumas)
    hh, pp = apply_coverage_scaling(hh, pp, coverage_fractions)
    # carry household geography onto persons (they only had SERIALNO)
    pp = pp.merge(hh[["SERIALNO", "puma_key"]], on="SERIALNO", how="left")
    return hh, pp
