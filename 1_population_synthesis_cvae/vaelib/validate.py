"""Comprehensive validation suite (12 categories) vs the held-out 2016 TEST split.

Marginals (F1), joints by order (F8), association (S3), income tail (F5), household
structure (S6), spatial (per-PUMA), structural zeros (=0), sampling zeros (recovered),
memorization, coherence, identifiability floors.
"""
from __future__ import annotations

import itertools
import numpy as np
import pandas as pd

from . import config
from .consistency import count_structural_zeros

HH_VARS = [("dwellingType", config.N_DWELLING_TYPES, 1), ("tenure", config.N_TENURE, 1),
           ("autos", config.N_AUTOS, 0), ("income_bin", config.n_hh_income_bins(), 0)]
PP_VARS = [("age_bin", config.N_AGE_BINS, 0), ("gender", config.N_GENDER, 1),
           ("race", config.N_RACE, 1), ("occupation", config.N_OCCUPATION, 1),
           ("driversLicense", config.N_LICENSE, 0), ("relationship", config.N_RELATIONSHIP, 0),
           ("nationality", config.N_NATIONALITY, 1), ("income_bin", config.n_pp_income_bins(), 0)]


def _dist(v, w, n, base):
    x = (pd.to_numeric(v, errors="coerce").fillna(base).astype(int) - base).clip(0, n - 1).to_numpy()
    h = np.bincount(x, weights=w, minlength=n).astype(float)
    return h / h.sum() if h.sum() > 0 else h


def tv(p, q): return 0.5 * np.abs(p - q).sum()
def srmse(p, q):
    d = p[p > 0].mean() if (p > 0).any() else 1.0
    return float(np.sqrt(np.mean((p - q) ** 2)) / d)


# ── F1 marginals ─────────────────────────────────────────────────────────
def marginals(gen, ref, refw, vars_):
    out = {}
    gw = np.ones(len(gen))
    for name, n, base in vars_:
        p = _dist(ref[name], refw, n, base); q = _dist(gen[name], gw, n, base)
        out[name] = {"tv": float(tv(p, q)), "srmse": srmse(p, q)}
    return out


# ── F8 joints by interaction order ───────────────────────────────────────
def _joint_dist(df, cols, ncs, w):
    idx = np.zeros(len(df), dtype=np.int64); mult = 1
    for (name, n, base) in reversed(cols):
        x = (pd.to_numeric(df[name], errors="coerce").fillna(base).astype(int) - base).clip(0, n - 1).to_numpy()
        idx = idx + x * mult; mult *= n
    h = np.bincount(idx, weights=w, minlength=mult).astype(float)
    return h / h.sum() if h.sum() > 0 else h


def joints_by_order(gen, ref, refw, vars_, orders=(1, 2, 3), max_combos=40):
    gw = np.ones(len(gen)); res = {}
    for o in orders:
        combos = list(itertools.combinations(vars_, o))[:max_combos]
        vals = []
        for c in combos:
            ncs = None
            p = _joint_dist(ref, list(c), ncs, refw); q = _joint_dist(gen, list(c), ncs, gw)
            vals.append(srmse(p, q))
        res[f"{o}way_mean_srmse"] = float(np.mean(vals)) if vals else float("nan")
    # worst 2-way pairs
    pairs = []
    for c in itertools.combinations(vars_, 2):
        p = _joint_dist(ref, list(c), None, refw); q = _joint_dist(gen, list(c), None, gw)
        pairs.append((f"{c[0][0]}×{c[1][0]}", srmse(p, q)))
    res["worst_pairs"] = sorted(pairs, key=lambda t: -t[1])[:5]
    return res


# ── F5 income tail ───────────────────────────────────────────────────────
def _wq(x, w, q):
    o = np.argsort(x); x, w = np.asarray(x)[o], np.asarray(w)[o]
    c = (np.cumsum(w) - 0.5 * w) / w.sum(); return float(np.interp(q, c, x))


def income_metrics(gen_hh, ref_hh, refw):
    g = gen_hh["income_hh"].to_numpy(); gw = np.ones(len(g))
    r = ref_hh["income_hh"].to_numpy()
    out = {}
    for q in (.5, .95, .99):
        rg, gg = _wq(r, refw, q), _wq(g, gw, q)
        out[f"P{int(q*100)}_bias_pct"] = float((gg - rg) / max(abs(rg), 1) * 100)
    out["share_gt_300k_ref"] = float(np.sum(refw[r > 3e5]) / refw.sum() * 100)
    out["share_gt_300k_gen"] = float((g > 3e5).mean() * 100)
    out["share_gt_1m_ref"] = float(np.sum(refw[r > 1e6]) / refw.sum() * 100)
    out["share_gt_1m_gen"] = float((g > 1e6).mean() * 100)
    out["max_ref"] = float(r.max()); out["max_gen"] = float(g.max())
    return out


# ── S6 household structure ───────────────────────────────────────────────
def couple_age_gap(pp, hh_col="hh_id"):
    cp = pp.loc[pp["relationship"].isin([0, 1]), [hh_col, "relationship", "age"]]
    # householder & spouse ages per household → |gap| where both present
    piv = cp.groupby([hh_col, "relationship"])["age"].first().unstack()
    if 0 not in piv.columns or 1 not in piv.columns:
        return float("nan")
    gaps = (piv[0] - piv[1]).abs().dropna()
    return float(gaps.mean()) if len(gaps) else float("nan")


# ── spatial: per-PUMA marginal SRMSE ─────────────────────────────────────
def per_puma_srmse(gen, ref, refw_col, vars_, level="hh"):
    res = {}
    for name, n, base in vars_:
        vals = []
        for pk in ref["puma_key"].unique():
            rsub = ref[ref["puma_key"] == pk]; gsub = gen[gen["puma_key"] == pk]
            if len(rsub) == 0 or len(gsub) == 0: continue
            p = _dist(rsub[name], rsub[refw_col].to_numpy(), n, base)
            q = _dist(gsub[name], np.ones(len(gsub)), n, base)
            vals.append(srmse(p, q))
        res[name] = float(np.mean(vals)) if vals else float("nan")
    return res


# ── S2 sampling zeros vs structural zeros ────────────────────────────────
def sampling_zeros(gen_pp, train_pp, test_pp, vars_=("age_bin", "occupation", "income_bin", "relationship")):
    def key(df):
        k = np.zeros(len(df), np.int64); m = 1
        for v in vars_:
            n = dict((nm, nn) for nm, nn, _ in PP_VARS)[v]
            x = pd.to_numeric(df[v], errors="coerce").fillna(0).astype(int).clip(0, n - 1).to_numpy()
            k = k + x * m; m *= n
        return set(np.unique(k).tolist())
    tr, te, ge = key(train_pp), key(test_pp), key(gen_pp)
    test_only = te - tr                       # sampling zeros (plausible, not in train)
    return {"cells_train": len(tr), "cells_test": len(te), "cells_gen": len(ge),
            "test_only_cells": len(test_only),
            "test_only_recovered_by_gen": len(test_only & ge),
            "recovery_rate": (len(test_only & ge) / len(test_only) if test_only else float("nan")),
            "novel_not_in_test": len(ge - te)}


# ── memorization ─────────────────────────────────────────────────────────
def memorization(gen_pp, train_pp, vars_=("age_bin", "gender", "race", "occupation",
                                          "driversLicense", "relationship", "income_bin")):
    def sig(df):
        return pd.util.hash_pandas_object(df[list(vars_)].astype(int), index=False)
    g = set(sig(gen_pp).tolist()); t = set(sig(train_pp).tolist())
    dup = len(g & t) / max(len(g), 1)
    return {"unique_gen_person_types": len(g), "frac_gen_types_in_train": float(dup)}


# ── coherence invariants ─────────────────────────────────────────────────
def coherence(gen_hh, gen_pp, zone_to_puma=None):
    sigma = (gen_pp.groupby("hh_id")["income"].sum() == gen_hh.set_index("hh_id")["income_hh"]).mean()
    nhead = gen_pp.groupby("hh_id")["relationship"].apply(lambda r: int((r == 0).sum()))
    return {"sigma_income_exact_pct": float(sigma * 100),
            "one_householder_pct": float((nhead == 1).mean() * 100)}
