"""Assign generated households to TAZ zones within their PUMA (HH-count weighted)."""
from __future__ import annotations

import numpy as np
import pandas as pd


class ZoneSampler:
    def __init__(self, zone_df: pd.DataFrame, weight_col="zone_weight_hh", rng=None):
        self.rng = rng or np.random.default_rng(0)
        self._zones, self._probs = {}, {}
        for pk, sub in zone_df.groupby("puma_key"):
            z = sub["zone_id"].to_numpy()
            w = np.maximum(sub[weight_col].to_numpy(float), 0.0)
            if w.sum() <= 0:
                w = np.ones_like(w)
            self._zones[pk] = z
            self._probs[pk] = w / w.sum()
        self._zone_to_county = {int(z): int(c) for z, c in
                                zip(zone_df["zone_id"], zone_df["county_fips"])}

    def has(self, pk): return pk in self._zones

    def assert_covered(self, pumas):
        missing = [pk for pk in pumas if pk not in self._zones]
        if missing:
            raise ValueError(f"{len(missing)} PUMAs missing from zone system, e.g. {missing[:5]}")

    def draw(self, puma_keys) -> np.ndarray:
        out = np.empty(len(puma_keys), dtype=np.int64)
        order = pd.Series(range(len(puma_keys))).groupby(list(puma_keys))
        for pk, idx in order.groups.items():
            idx = np.asarray(idx)
            out[idx] = self.rng.choice(self._zones[pk], size=len(idx), p=self._probs[pk])
        return out

    def county_of(self, zone_ids):
        return np.array([self._zone_to_county.get(int(z), 0) for z in zone_ids], dtype=np.int64)
