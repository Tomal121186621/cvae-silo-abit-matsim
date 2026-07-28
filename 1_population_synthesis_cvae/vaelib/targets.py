"""Per-PUMA weighted marginal targets for the (tunable) marginal-JSD loss and validation.

All-categorical, including the HH and person income BINS. No Pareto bounds (income is binned).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

__all__ = ["MARGINAL_SCHEMA", "weighted_distribution", "build_puma_targets",
           "save_targets", "load_targets"]


def _schema():
    """(name, n_cats, base, level) for every modeled categorical, incl income bins."""
    return [
        ("dwellingType", config.N_DWELLING_TYPES, 1, "hh"),
        ("tenure",       config.N_TENURE,         1, "hh"),
        ("autos",        config.N_AUTOS,          0, "hh"),
        ("income_bin",   config.n_hh_income_bins(), 0, "hh"),
        ("age_bin",      config.N_AGE_BINS,       0, "pp"),
        ("gender",       config.N_GENDER,         1, "pp"),
        ("race",         config.N_RACE,           1, "pp"),
        ("occupation",   config.N_OCCUPATION,     1, "pp"),
        ("driversLicense", config.N_LICENSE,      0, "pp"),
        ("relationship", config.N_RELATIONSHIP,   0, "pp"),
        ("nationality", config.N_NATIONALITY,     1, "pp"),
        ("pp_income_bin", config.n_pp_income_bins(), 0, "pp"),  # person income bin
    ]


MARGINAL_SCHEMA = _schema()


def weighted_distribution(values, weights, n_cats, base) -> list[float]:
    v = (pd.to_numeric(pd.Series(values), errors="coerce").fillna(base).astype(int) - base)
    v = v.clip(0, n_cats - 1).to_numpy()
    w = pd.to_numeric(pd.Series(weights), errors="coerce").fillna(0.0).to_numpy()
    hist = np.bincount(v, weights=w, minlength=n_cats).astype(float)
    s = hist.sum()
    return (hist / s).tolist() if s > 0 else [0.0] * n_cats


def build_puma_targets(hh: pd.DataFrame, pp: pd.DataFrame, mstm_pumas) -> dict:
    """Return {puma_key: {var_name: [probabilities]}} for every PUMA in mstm_pumas."""
    hh_g = {pk: sub for pk, sub in hh.groupby("puma_key")}
    pp_g = {pk: sub for pk, sub in pp.groupby("puma_key")}
    targets: dict = {}
    for pk in mstm_pumas:
        d: dict = {}
        h = hh_g.get(pk); p = pp_g.get(pk)
        for name, n_cats, base, level in MARGINAL_SCHEMA:
            if level == "hh":
                if h is None or len(h) == 0:
                    continue
                d[name] = weighted_distribution(h[name], h["WGTP_eff"], n_cats, base)
            else:
                if p is None or len(p) == 0:
                    continue
                col = "income_bin" if name == "pp_income_bin" else name
                d[name] = weighted_distribution(p[col], p["PWGTP_eff"], n_cats, base)
        targets[pk] = d
    return targets


def save_targets(targets: dict, path: Path) -> Path:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(targets, indent=1, sort_keys=True))
    return Path(path)


def load_targets(path: Path) -> dict:
    return json.loads(Path(path).read_text())
