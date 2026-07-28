"""Geography crosswalks: zone table, PUMA↔zone↔county, coverage, PUMA index.

Zone system columns used: ZoneId, STATEFP10, PUMA_10, COUNTYFIPS, AREA_SQMI.
HH-count weights from Activities_2016.csv (SMZ_N → HH16); zones missing a count get an
area × PUMA-density estimate (same units, so within-PUMA normalization is unit-consistent).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

__all__ = ["build_zone_table", "build_puma_zone_lookup", "build_zone_to_county",
           "load_coverage_fractions", "build_puma_to_idx", "load_hh_counts", "mstm_puma_set"]


def load_coverage_fractions(path=config.COVERAGE_JSON) -> dict:
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def load_hh_counts(path=config.ACTIVITIES_CSV) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    df = pd.read_csv(p)
    zcol = "SMZ_N" if "SMZ_N" in df.columns else df.columns[0]
    hcol = "HH16" if "HH16" in df.columns else df.columns[-1]
    return {int(z): float(h) for z, h in zip(df[zcol], df[hcol]) if pd.notna(z)}


def build_zone_table(zone_system_csv=config.ZONE_SYSTEM_CSV, hh_counts: dict | None = None) -> pd.DataFrame:
    df = pd.read_csv(zone_system_csv)
    out = pd.DataFrame()
    out["zone_id"] = pd.to_numeric(df["ZoneId"], errors="coerce").astype(int)
    state = pd.to_numeric(df["STATEFP10"], errors="coerce").astype(int)
    puma10 = pd.to_numeric(df["PUMA_10"], errors="coerce").astype(int)
    puma5 = (puma10 % 100_000)
    out["puma_key"] = [config.puma_key(s, p) for s, p in zip(state, puma5)]
    out["county_fips"] = pd.to_numeric(df["COUNTYFIPS"], errors="coerce").fillna(0).astype(int)
    out["area_sqmi"] = pd.to_numeric(df.get("AREA_SQMI", 1.0), errors="coerce").fillna(0.0)

    if hh_counts is None:
        hh_counts = load_hh_counts()
    out["hh_count"] = out["zone_id"].map(hh_counts).astype(float)
    # area × PUMA-density estimate for zones missing a count (unit-consistent within PUMA)
    have = out["hh_count"].notna() & (out["hh_count"] > 0)
    dens = (out.loc[have].groupby("puma_key")
            .apply(lambda g: g["hh_count"].sum() / max(g["area_sqmi"].sum(), 1e-9), include_groups=False))
    est = out["area_sqmi"] * out["puma_key"].map(dens).fillna(0.0)
    out["zone_weight_hh"] = np.where(have, out["hh_count"].fillna(0.0), est)
    # any PUMA with no counts at all → fall back to area
    bad = out.groupby("puma_key")["zone_weight_hh"].transform("sum") <= 0
    out.loc[bad, "zone_weight_hh"] = out.loc[bad, "area_sqmi"].clip(lower=1e-6)
    out["n_hh_count_fallback"] = (~have).sum()
    return out


def build_puma_zone_lookup(zone_df: pd.DataFrame) -> dict:
    return {pk: sub["zone_id"].tolist() for pk, sub in zone_df.groupby("puma_key")}


def build_zone_to_county(zone_df: pd.DataFrame) -> dict:
    fold = config.VA_INDEPENDENT_CITIES
    return {int(z): int(fold.get(int(c), int(c)))
            for z, c in zip(zone_df["zone_id"], zone_df["county_fips"])}


def build_puma_to_idx(pumas) -> dict:
    return {pk: i for i, pk in enumerate(sorted(set(pumas)))}


def mstm_puma_set(zone_system_csv=config.ZONE_SYSTEM_CSV) -> set:
    return set(build_zone_table(zone_system_csv)["puma_key"].unique())
