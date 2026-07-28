"""Generate a synthetic population from the trained simple CVAE.

Flow: build (PUMA, size) conditioning → model.sample bins → decode to values →
exact age within bin → within-(PUMA,bin) empirical income draw → enforce constraints →
reconcile Σ person == HH income → assign zones. No income head; income is binned + drawn.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from . import config
from .consistency import apply_constraints, enforce_one_householder
from .income_bins import WithinBinSampler, reconcile_pp_to_hh
from .model import CVAE, hh_cat_vars, pp_cat_vars


def build_conditioning(hh: pd.DataFrame, puma_to_idx: dict, n_total: int, rng) -> tuple:
    """Sample (puma_key, size) for n_total households ∝ weighted (PUMA,size) frequency."""
    key = hh["puma_key"].to_numpy()
    size = pd.to_numeric(hh["hhSizeVAE"], errors="coerce").fillna(1).astype(int).clip(1, config.S_MAX).to_numpy()
    w = pd.to_numeric(hh["WGTP_eff"], errors="coerce").fillna(0.0).to_numpy()
    p = w / w.sum()
    pick = rng.choice(len(hh), size=n_total, replace=True, p=p)
    return key[pick], size[pick]


def generate_population(model: CVAE, hh_pre: pd.DataFrame, pp_pre: pd.DataFrame,
                        puma_to_idx: dict, zone_sampler, n_total: int | None = None,
                        temperature: float = 1.0, seed: int = 0, device: str = "cpu",
                        batch_size: int = 8192):
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    if n_total is None:
        n_total = int(round(hh_pre["WGTP_eff"].sum()))
    puma_keys, sizes = build_conditioning(hh_pre, puma_to_idx, n_total, rng)
    inv_puma = {v: k for k, v in puma_to_idx.items()}
    puma_idx_all = np.array([puma_to_idx[k] for k in puma_keys])

    hh_vars, pp_vars = hh_cat_vars(), pp_cat_vars()
    hh_chunks, pp_chunks = [], []
    model.eval()
    for start in range(0, n_total, batch_size):
        end = min(start + batch_size, n_total)
        pidx = torch.as_tensor(puma_idx_all[start:end], dtype=torch.long, device=device)
        sidx = torch.as_tensor(sizes[start:end], dtype=torch.long, device=device)
        hh_s, pp_s = model.sample(pidx, sidx, temperature=temperature)
        hh_s, pp_s = hh_s.cpu().numpy(), pp_s.cpu().numpy()
        b = hh_s.shape[0]
        hid = np.arange(start, end) + 1
        pk = puma_keys[start:end]; sz = sizes[start:end]

        hh_d = {"hh_id": hid, "puma_key": pk, "hhSize": sz}
        for k, (name, _, base) in enumerate(hh_vars):
            hh_d[name] = hh_s[:, k] + (base if name != "income_bin" else 0)
        hh_chunks.append(pd.DataFrame(hh_d))

        # vectorized person expansion: repeat each HH by its size, gather slot values
        row_rep = np.repeat(np.arange(b), sz)
        slot_rep = np.concatenate([np.arange(s) for s in sz]) if b else np.array([], int)
        pp_d = {"hh_id": np.repeat(hid, sz), "puma_key": np.repeat(pk, sz),
                "sporder": slot_rep + 1}
        for k, (name, _, base) in enumerate(pp_vars):
            pp_d[name] = pp_s[row_rep, slot_rep, k] + (base if name != "income_bin" else 0)
        pp_chunks.append(pd.DataFrame(pp_d))

    gen_hh = pd.concat(hh_chunks, ignore_index=True)
    gen_pp = pd.concat(pp_chunks, ignore_index=True)
    gen_pp.insert(0, "pp_id", np.arange(1, len(gen_pp) + 1))

    # exact age within the 5-year bin (85+ bin → 85..99)
    ab = gen_pp["age_bin"].to_numpy()
    lo = ab * 5; span = np.where(ab >= 17, 15, 5)
    gen_pp["age"] = (lo + rng.integers(0, span)).clip(0, 99)

    # within-(PUMA,bin) empirical income draw
    hh_edges, pp_edges = config.load_income_bin_edges()
    hh_samp = WithinBinSampler(hh_pre["income_hh"], hh_pre["puma_key"],
                               hh_pre["income_bin"], hh_pre["WGTP_eff"], hh_edges, rng)
    pp_samp = WithinBinSampler(pp_pre["income"], pp_pre["puma_key"],
                               pp_pre["income_bin"], pp_pre["PWGTP_eff"], pp_edges, rng)
    gen_hh["income_hh"] = hh_samp.sample(gen_hh["puma_key"].to_numpy(),
                                         gen_hh["income_bin"].to_numpy()).round().astype(int)
    gen_pp["income"] = pp_samp.sample(gen_pp["puma_key"].to_numpy(),
                                      gen_pp["income_bin"].to_numpy()).round().astype(int)

    # enforce structural constraints: age-based rules + exactly one householder per HH.
    # First record the PRE-patch illegal-combination rate -- the informative number
    # (the post-patch count is 0 by construction, i.e. tautological). Stashed on
    # gen_pp.attrs so the validator can report both. See consistency.py / README.
    from .consistency import count_structural_zeros as _csz
    _pre = _csz(gen_pp)   # hh=None: the age/license/spouse illegal-combos apply_constraints overwrites
    _pre["rate_pct"] = 100.0 * _pre["total"] / max(len(gen_pp), 1)
    gen_pp.attrs["prepatch_structural_zeros"] = _pre
    gen_pp.attrs["n_persons"] = int(len(gen_pp))
    gen_pp = apply_constraints(gen_pp)
    gen_pp = enforce_one_householder(gen_pp)

    # reconcile Σ person income == HH income (rank-preserving, earners only)
    gen_pp = _reconcile(gen_hh, gen_pp)

    # assign zones within PUMA + county
    zone_sampler.assert_covered(gen_hh["puma_key"].unique())
    gen_hh["zone_id"] = zone_sampler.draw(gen_hh["puma_key"].to_numpy())
    gen_hh["county_fips"] = zone_sampler.county_of(gen_hh["zone_id"].to_numpy())
    return gen_hh, gen_pp


def _reconcile(gen_hh, gen_pp):
    """Scale person incomes to sum to HH income, preserving the model's income recipients
    (anyone the model gave a positive income — retirees/students included, not just employed)."""
    hh_income = gen_hh.set_index("hh_id")["income_hh"].to_dict()
    out = gen_pp.copy()
    new_inc = out["income"].to_numpy().astype(np.int64).copy()
    for hid, grp in out.groupby("hh_id", sort=False):
        idx = grp.index.to_numpy()
        recipient = new_inc[idx] > 0                  # the model's predicted income recipients
        rec = reconcile_pp_to_hh(new_inc[idx], hh_income.get(hid, 0),
                                 earner_mask=recipient if recipient.any() else None)
        new_inc[idx] = rec
    out["income"] = new_inc
    return out
