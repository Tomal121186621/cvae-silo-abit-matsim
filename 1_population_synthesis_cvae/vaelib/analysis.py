"""Raw-ACS statistical analysis + visualization helpers (the pre-preprocessing gate).

Weighted univariate descriptive statistics for every source variable the VAE uses,
income tail diagnostics (log-log CCDF, Hill, mean-excess), the age lifecycle, and an
income-bin occupancy report used to finalize the (data-driven) bin edges.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ── weighted moment helpers ──────────────────────────────────────────────
def wmean(x, w): return float(np.sum(w * x) / np.sum(w))
def wstd(x, w, m=None):
    m = wmean(x, w) if m is None else m
    return float(np.sqrt(np.sum(w * (x - m) ** 2) / np.sum(w)))
def wmoment(x, w, k, m=None, s=None):
    m = wmean(x, w) if m is None else m
    s = wstd(x, w, m) if s is None else s
    return float(np.sum(w * ((x - m) / s) ** k) / np.sum(w))
def wquantile(x, w, q):
    o = np.argsort(x); x, w = np.asarray(x)[o], np.asarray(w)[o]
    c = (np.cumsum(w) - 0.5 * w) / np.sum(w)
    return float(np.interp(q, c, x))


def continuous_stats(values: pd.Series, weights: pd.Series) -> dict:
    raw = pd.to_numeric(values, errors="coerce")
    valid = raw.notna()
    x = raw[valid].to_numpy(float); w = pd.to_numeric(weights, errors="coerce")[valid].to_numpy(float)
    m = wmean(x, w); s = wstd(x, w, m)
    qs = {q: wquantile(x, w, q) for q in (.01, .05, .25, .5, .75, .95, .99)}
    return dict(type="continuous", n_valid=int(valid.sum()), null_pct=float((~valid).mean() * 100),
                mean=m, median=qs[.5], std=s, cv=(s / m if m else float("nan")),
                skew=wmoment(x, w, 3, m, s), kurtosis=wmoment(x, w, 4, m, s) - 3,
                min=float(x.min()), p1=qs[.01], p5=qs[.05], p25=qs[.25], p75=qs[.75],
                p95=qs[.95], p99=qs[.99], max=float(x.max()),
                zero_neg_pct=float(np.sum(w[x <= 0]) / np.sum(w) * 100))


def categorical_stats(values: pd.Series, weights: pd.Series) -> tuple[dict, pd.Series]:
    raw = pd.to_numeric(values, errors="coerce")
    g = pd.Series(pd.to_numeric(weights, errors="coerce").values).groupby(raw.values).sum().sort_index()
    pct = g / g.sum() * 100
    ent = float(-(pct / 100 * np.log2(pct / 100 + 1e-12)).sum())
    summary = dict(type="categorical", n_categories=int(len(g)),
                   null_pct=float(raw.isna().mean() * 100), mode=float(g.idxmax()),
                   mode_pct=float(pct.max()), entropy_bits=ent,
                   max_entropy_bits=float(np.log2(len(g))) if len(g) > 1 else 0.0)
    return summary, pct


def hill_alpha(values, w, u):
    """Weighted-record Hill estimator of the Pareto tail index above threshold u."""
    x = np.asarray(values, float)
    y = x[x > u]
    if len(y) < 5:
        return float("nan"), 0
    return float(len(y) / np.sum(np.log(y / u))), int(len(y))


def income_bin_occupancy(income, weights, edges):
    """Weighted share of records in each [edge_i, edge_{i+1}) bin."""
    x = pd.to_numeric(income, errors="coerce")
    w = pd.to_numeric(weights, errors="coerce")
    m = x.notna() & w.notna()
    idx = np.searchsorted(np.asarray(edges, float), x[m].to_numpy(float), side="right") - 1
    idx = np.clip(idx, 0, len(edges) - 2)
    occ = pd.Series(w[m].to_numpy(float)).groupby(idx).sum()
    occ = occ.reindex(range(len(edges) - 1), fill_value=0.0)
    return (occ / occ.sum() * 100).to_numpy()
