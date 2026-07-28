"""Donor-fill structural dwelling attributes (bedrooms, monthlyCost, yearBuilt) — not modeled
by the VAE; sample from a matching PUMS household via cascading match keys (vectorized)."""
from __future__ import annotations

import numpy as np
import pandas as pd

DD_COLS = ["bedrooms", "monthlyCost", "yearBuilt"]
_KEYS = [["puma_key", "dwellingType", "tenure", "income_bin"],
         ["puma_key", "dwellingType", "tenure"],
         ["dwellingType", "tenure"]]


def fill_dwelling_attrs(gen_hh: pd.DataFrame, pums_hh: pd.DataFrame, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(gen_hh)
    out = np.zeros((n, len(DD_COLS)), dtype=np.int64)
    filled = np.zeros(n, dtype=bool)
    src = pums_hh[["puma_key", "dwellingType", "tenure", "income_bin"] + DD_COLS]

    for key in _KEYS:
        if filled.all():
            break
        pool = {g: sub[DD_COLS].to_numpy() for g, sub in src.groupby(key)}
        gkey = pd.MultiIndex.from_frame(gen_hh[key]).to_numpy() if len(key) > 1 else gen_hh[key[0]].to_numpy()
        rem = pd.DataFrame({"i": np.arange(n)[~filled],
                            "k": (gkey[~filled])})
        for g, grp in rem.groupby("k", sort=False):
            arr = pool.get(g)
            if arr is None or len(arr) == 0:
                continue
            ix = grp["i"].to_numpy()
            out[ix] = arr[rng.integers(len(arr), size=len(ix))]
            filled[ix] = True

    # global fallback for any still-unfilled
    if not filled.all():
        arr = src[DD_COLS].to_numpy()
        ix = np.where(~filled)[0]
        out[ix] = arr[rng.integers(len(arr), size=len(ix))]

    gen_hh = gen_hh.copy()
    for j, c in enumerate(DD_COLS):
        gen_hh[c] = out[:, j]
    return gen_hh
