"""Income binning + within-bin empirical recovery (the only 'special' income code).

- `to_bin(values, edges)`  : continuous income -> bin index (vectorized).
- `WithinBinSampler`       : draw real $ from the empirical records in a (PUMA, bin) cell;
                             the open top bin returns the genuine high incomes (built step 02).
- `reconcile_pp_to_hh`     : rank-preserving largest-remainder so Σ person == HH income.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["to_bin", "WithinBinSampler", "reconcile_pp_to_hh"]


def to_bin(values, edges) -> np.ndarray:
    """Map income to bin index in [0, len(edges)-2]. Edges are right-open [e_i, e_{i+1})."""
    x = pd.to_numeric(pd.Series(values), errors="coerce").fillna(0).to_numpy(float)
    edges = np.asarray(edges, float)
    idx = np.searchsorted(edges, x, side="right") - 1
    return np.clip(idx, 0, len(edges) - 2).astype(np.int64)


class WithinBinSampler:
    """Empirical income recovery: for a (PUMA, bin) draw a real value from the PUMS records
    that fell in that cell. Falls back to bin-level (any PUMA), then bin midpoint."""

    def __init__(self, income, puma_key, bin_idx, weights, edges, rng=None):
        self.edges = np.asarray(edges, float)
        self.rng = rng or np.random.default_rng(0)
        df = pd.DataFrame({"inc": np.asarray(income, float),
                           "puma": np.asarray(puma_key),
                           "bin": np.asarray(bin_idx, int),
                           "w": np.asarray(weights, float)})
        df = df[df["w"] > 0]
        # pools keyed by (puma, bin) and by bin; store values + normalized weights
        self._by_pb: dict = {}
        self._by_b: dict = {}
        for key, sub in df.groupby(["puma", "bin"]):
            self._by_pb[key] = (sub["inc"].to_numpy(), (sub["w"] / sub["w"].sum()).to_numpy())
        for b, sub in df.groupby("bin"):
            self._by_b[int(b)] = (sub["inc"].to_numpy(), (sub["w"] / sub["w"].sum()).to_numpy())

    def _midpoint(self, b: int) -> float:
        lo, hi = self.edges[b], self.edges[b + 1]
        if not np.isfinite(lo): lo = hi - 1.0
        if not np.isfinite(hi): hi = lo * 1.5 if lo > 0 else 1.0
        return float((lo + hi) / 2.0)

    def sample(self, puma_keys, bin_idx) -> np.ndarray:
        """Vectorized: one rng.choice per (puma, bin) group instead of per record."""
        puma_keys = np.asarray(puma_keys); bin_idx = np.asarray(bin_idx, int)
        out = np.empty(len(bin_idx), dtype=float)
        df = pd.DataFrame({"pk": puma_keys, "b": bin_idx, "i": np.arange(len(bin_idx))})
        for (pk, b), grp in df.groupby(["pk", "b"], sort=False):
            ix = grp["i"].to_numpy()
            pool = self._by_pb.get((pk, int(b))) or self._by_b.get(int(b))
            if pool is None:
                out[ix] = self._midpoint(int(b))
            else:
                vals, p = pool
                out[ix] = self.rng.choice(vals, size=len(ix), p=p)
        return out


def reconcile_pp_to_hh(pp_income: np.ndarray, hh_total: float, earner_mask=None) -> np.ndarray:
    """Scale person incomes so they sum EXACTLY to hh_total (integer, rank-preserving via
    largest-remainder). Non-earners (mask False) stay 0; if all zero, dump to first eligible."""
    inc = np.maximum(np.asarray(pp_income, float), 0.0)
    if earner_mask is not None:
        inc = np.where(np.asarray(earner_mask, bool), inc, 0.0)
    target = int(round(hh_total))
    s = inc.sum()
    if target <= 0:
        return np.zeros_like(inc, dtype=np.int64)
    if s <= 0:
        out = np.zeros_like(inc, dtype=np.int64)
        j = (np.argmax(earner_mask) if earner_mask is not None and np.any(earner_mask) else 0)
        out[j] = target
        return out
    scaled = inc * (target / s)
    floor = np.floor(scaled).astype(np.int64)
    rem = target - int(floor.sum())
    if rem > 0:
        order = np.argsort(-(scaled - floor))   # largest fractional remainder first
        floor[order[:rem]] += 1
    elif rem < 0:
        order = np.argsort(scaled - floor)
        k = 0
        while rem < 0 and k < len(order):
            if floor[order[k]] > 0:
                floor[order[k]] -= 1; rem += 1
            k += 1
    return floor
