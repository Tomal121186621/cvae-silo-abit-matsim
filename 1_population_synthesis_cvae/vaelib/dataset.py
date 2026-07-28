"""Build CVAE tensors from preprocessed frames + the per-PUMA 80/10/10 household-level split.

Persons are ordered canonically (householder first, then SPORDER), padded to S_MAX, masked.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader

from . import config
from .model import CVAEBatch, hh_cat_vars, pp_cat_vars

S = config.S_MAX


def build_arrays(hh: pd.DataFrame, pp: pd.DataFrame, puma_to_idx: dict) -> dict:
    hh = hh.reset_index(drop=True)
    N = len(hh)
    hh_vars, pp_vars = hh_cat_vars(), pp_cat_vars()

    # HH index array (0-indexed per var)
    HH = np.zeros((N, len(hh_vars)), dtype=np.int64)
    for k, (name, n, base) in enumerate(hh_vars):
        HH[:, k] = (pd.to_numeric(hh[name], errors="coerce").fillna(base).astype(int) - base).clip(0, n - 1)

    PUMA = hh["puma_key"].map(puma_to_idx).fillna(0).astype(int).to_numpy()
    SIZE = pd.to_numeric(hh["hhSizeVAE"], errors="coerce").fillna(1).astype(int).clip(1, S).to_numpy()
    W = pd.to_numeric(hh["WGTP_eff"], errors="coerce").fillna(0.0).to_numpy(float)

    # persons → slots
    ser_to_row = {s: i for i, s in enumerate(hh["SERIALNO"].to_numpy())}
    p = pp.copy()
    p["_row"] = p["SERIALNO"].map(ser_to_row)
    p = p[p["_row"].notna()].copy(); p["_row"] = p["_row"].astype(int)
    p["_hhfirst"] = (pd.to_numeric(p["relationship"], errors="coerce").fillna(7) != 0).astype(int)
    p = p.sort_values(["_row", "_hhfirst", "SPORDER"], kind="stable")
    p["_slot"] = p.groupby("_row").cumcount()
    p = p[p["_slot"] < S]
    rows = p["_row"].to_numpy(); slots = p["_slot"].to_numpy()

    PP = np.zeros((N, S, len(pp_vars)), dtype=np.int64)
    for k, (name, n, base) in enumerate(pp_vars):
        vals = (pd.to_numeric(p[name], errors="coerce").fillna(base).astype(int) - base).clip(0, n - 1).to_numpy()
        PP[rows, slots, k] = vals
    MASK = np.zeros((N, S), dtype=bool)
    MASK[rows, slots] = True
    return {"HH": HH, "PP": PP, "MASK": MASK, "PUMA": PUMA, "SIZE": SIZE, "W": W,
            "serialno": hh["SERIALNO"].to_numpy()}


def stratified_split(hh: pd.DataFrame, fracs=(0.8, 0.1, 0.1), seed=0):
    """Per-PUMA household-level split → (train_idx, val_idx, test_idx) into hh row order."""
    rng = np.random.default_rng(seed)
    hh = hh.reset_index(drop=True)
    tr, va, te = [], [], []
    for _, sub in hh.groupby("puma_key"):
        idx = sub.index.to_numpy().copy(); rng.shuffle(idx)
        n = len(idx); n_tr = int(round(n * fracs[0])); n_va = int(round(n * fracs[1]))
        tr += idx[:n_tr].tolist(); va += idx[n_tr:n_tr + n_va].tolist(); te += idx[n_tr + n_va:].tolist()
    return np.array(sorted(tr)), np.array(sorted(va)), np.array(sorted(te))


class CVAEDataset(Dataset):
    def __init__(self, arrays: dict, indices: np.ndarray):
        self.a = arrays; self.idx = np.asarray(indices)

    def __len__(self): return len(self.idx)

    def __getitem__(self, i):
        j = self.idx[i]
        a = self.a
        return (a["HH"][j], a["PP"][j], a["MASK"][j], a["PUMA"][j], a["SIZE"][j], a["W"][j])


def collate(items) -> CVAEBatch:
    HH, PP, MASK, PUMA, SIZE, W = zip(*items)
    return CVAEBatch(
        hh_idx=torch.as_tensor(np.stack(HH), dtype=torch.long),
        pp_idx=torch.as_tensor(np.stack(PP), dtype=torch.long),
        pp_mask=torch.as_tensor(np.stack(MASK), dtype=torch.bool),
        puma_idx=torch.as_tensor(np.array(PUMA), dtype=torch.long),
        size_idx=torch.as_tensor(np.array(SIZE), dtype=torch.long),
        w=torch.as_tensor(np.array(W), dtype=torch.float32),
    )


def make_loader(arrays, indices, batch_size=512, shuffle=False):
    return DataLoader(CVAEDataset(arrays, indices), batch_size=batch_size,
                      shuffle=shuffle, collate_fn=collate)
