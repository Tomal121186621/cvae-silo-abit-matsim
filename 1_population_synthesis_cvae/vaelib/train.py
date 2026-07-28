"""Trainer for the simple CVAE: CE recon + KL(free-bits) + optional marginal-JSD, with
β-annealing, EMA, early stopping, and a per-epoch validation joint-SRMSE monitor.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from . import config
from .model import CVAE, CVAEConfig, hh_cat_vars, pp_cat_vars


def set_seed(seed: int):
    import random
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)


@dataclass
class TrainConfig:
    max_epochs: int = 300
    lr: float = 1e-3
    weight_decay: float = 1e-5
    kl_anneal_epochs: int = 30
    kl_max_beta: float = 1.0
    patience: int = 25
    min_delta: float = 1e-4
    ema_decay: float = 0.999
    seed: int = 0
    device: str = "cpu"
    joint_eval_every: int = 5


# ── marginal target tensors for the JSD term ─────────────────────────────
def build_marginal_tensors(puma_targets: dict, puma_to_idx: dict, device="cpu") -> dict:
    n_pumas = len(puma_to_idx)
    names = {"dwellingType": config.N_DWELLING_TYPES, "tenure": config.N_TENURE,
             "autos": config.N_AUTOS, "income_bin": config.n_hh_income_bins(),
             "age_bin": config.N_AGE_BINS, "gender": config.N_GENDER, "race": config.N_RACE,
             "occupation": config.N_OCCUPATION, "driversLicense": config.N_LICENSE,
             "relationship": config.N_RELATIONSHIP, "nationality": config.N_NATIONALITY,
             "pp_income_bin": config.n_pp_income_bins()}
    out = {k: torch.zeros(n_pumas, n, device=device) for k, n in names.items()}
    for pk, idx in puma_to_idx.items():
        d = puma_targets.get(pk, {})
        for k in names:
            if k in d and len(d[k]) == names[k]:
                out[k][idx] = torch.tensor(d[k], dtype=torch.float32, device=device)
    return out


# ── joint-SRMSE monitor (does the model learn joints?) ───────────────────
_JOINTS = [("hh", "dwellingType", "tenure"), ("hh", "autos", "income_bin"),
           ("pp", "age_bin", "income_bin"), ("pp", "occupation", "income_bin")]


def _joint_hist(a_idx, b_idx, na, nb, w=None):
    flat = a_idx * nb + b_idx
    h = np.bincount(flat, weights=w, minlength=na * nb).astype(float)
    s = h.sum()
    return h / s if s > 0 else h


def compute_joint_srmse(model, arrays, idx, device="cpu", max_n=20000, seed=0) -> float:
    from .dataset import CVAEDataset, collate
    rng = np.random.default_rng(seed)
    sub = idx if len(idx) <= max_n else rng.choice(idx, max_n, replace=False)
    items = [CVAEDataset(arrays, sub)[i] for i in range(len(sub))]
    b = collate(items)
    model.eval()
    with torch.no_grad():
        hh_s, pp_s = model.sample(b.puma_idx.to(device), b.size_idx.to(device), temperature=1.0)
    hh_s, pp_s = hh_s.cpu().numpy(), pp_s.cpu().numpy()
    hhv = {n: k for k, (n, _, _) in enumerate(hh_cat_vars())}
    ppv = {n: k for k, (n, _, _) in enumerate(pp_cat_vars())}
    ncat_hh = {n: c for n, c, _ in hh_cat_vars()}      # distinct: both levels have income_bin
    ncat_pp = {n: c for n, c, _ in pp_cat_vars()}
    mask = b.pp_mask.numpy(); w = b.w.numpy()
    srmses = []
    for level, va, vb in _JOINTS:
        nc = ncat_hh if level == "hh" else ncat_pp
        na, nb = nc[va], nc[vb]
        if level == "hh":
            tgt = _joint_hist(b.hh_idx[:, hhv[va]].numpy(), b.hh_idx[:, hhv[vb]].numpy(), na, nb, w)
            gen = _joint_hist(hh_s[:, hhv[va]], hh_s[:, hhv[vb]], na, nb)
        else:
            m = mask.reshape(-1)
            ta = b.pp_idx[:, :, ppv[va]].numpy().reshape(-1)[m]
            tb = b.pp_idx[:, :, ppv[vb]].numpy().reshape(-1)[m]
            wp = np.repeat(w, model.S)[m]
            tgt = _joint_hist(ta, tb, na, nb, wp)
            ga = pp_s[:, :, ppv[va]].reshape(-1)[m]; gb = pp_s[:, :, ppv[vb]].reshape(-1)[m]
            gen = _joint_hist(ga, gb, na, nb)
        denom = tgt[tgt > 0].mean() if (tgt > 0).any() else 1.0
        srmses.append(float(np.sqrt(np.mean((tgt - gen) ** 2)) / denom))
    return float(np.mean(srmses))


class EMA:
    def __init__(self, model, decay):
        self.decay = decay
        self.shadow = {n: p.detach().clone() for n, p in model.named_parameters()}

    def update(self, model):
        for n, p in model.named_parameters():
            self.shadow[n].mul_(self.decay).add_(p.detach(), alpha=1 - self.decay)

    def copy_to(self, model):
        for n, p in model.named_parameters():
            p.data.copy_(self.shadow[n])


class Trainer:
    def __init__(self, model: CVAE, arrays, train_idx, val_idx, tcfg: TrainConfig,
                 out_dir: Path, marg=None):
        self.m = model.to(tcfg.device); self.a = arrays
        self.tr, self.va = train_idx, val_idx
        self.cfg = tcfg; self.out = Path(out_dir); self.out.mkdir(parents=True, exist_ok=True)
        self.marg = marg
        self.opt = torch.optim.AdamW(model.parameters(), lr=tcfg.lr, weight_decay=tcfg.weight_decay)
        self.ema = EMA(model, tcfg.ema_decay)
        self.history = []

    def _loader(self, idx, shuffle):
        from .dataset import make_loader
        return make_loader(self.a, idx, batch_size=512, shuffle=shuffle)

    def _run_epoch(self, loader, beta, train: bool):
        self.m.train(train)
        agg = {"loss": 0, "recon": 0, "kl": 0, "jsd": 0, "kl_active_dims": 0, "n": 0}
        for b in loader:
            b = self._to(b)
            if train:
                self.opt.zero_grad()
            loss, parts = self.m.compute_loss(b, beta=beta, marg=self.marg)
            if train:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.m.parameters(), 1.0)
                self.opt.step(); self.ema.update(self.m)
            for k in ("recon", "kl", "jsd"):
                agg[k] += parts[k]
            agg["loss"] += float(loss.detach()); agg["kl_active_dims"] = parts["kl_active_dims"]; agg["n"] += 1
        for k in ("loss", "recon", "kl", "jsd"):
            agg[k] /= max(agg["n"], 1)
        return agg

    def _to(self, b):
        d = self.cfg.device
        from .model import CVAEBatch
        return CVAEBatch(b.hh_idx.to(d), b.pp_idx.to(d), b.pp_mask.to(d),
                         b.puma_idx.to(d), b.size_idx.to(d), b.w.to(d))

    def train(self):
        set_seed(self.cfg.seed)
        tl, vl = self._loader(self.tr, True), self._loader(self.va, False)
        best, best_ep, since = float("inf"), -1, 0
        for ep in range(self.cfg.max_epochs):
            beta = min(self.cfg.kl_max_beta, self.cfg.kl_max_beta * (ep + 1) / max(self.cfg.kl_anneal_epochs, 1))
            tr = self._run_epoch(tl, beta, True)
            va = self._run_epoch(vl, beta, False)
            # selection/reporting use the β=1 ELBO (recon+KL) — comparable across epochs,
            # unlike the annealed objective which rises as β ramps 0→1.
            tr_elbo = tr["recon"] + tr["kl"]; va_elbo = va["recon"] + va["kl"]
            row = {"epoch": ep, "beta": beta,
                   "train_total": tr_elbo, "val_total": va_elbo,
                   "train_total_annealed": tr["loss"], "val_total_annealed": va["loss"],
                   "train_recon": tr["recon"], "val_recon": va["recon"],
                   "train_kl": tr["kl"], "val_kl": va["kl"], "train_jsd": tr["jsd"],
                   "kl_active_dims": va["kl_active_dims"]}
            if ep % self.cfg.joint_eval_every == 0 or ep == self.cfg.max_epochs - 1:
                row["val_joint_srmse"] = compute_joint_srmse(self.m, self.a, self.va, self.cfg.device)
            self.history.append(row)
            improved = va_elbo < best - self.cfg.min_delta
            if improved:
                best, best_ep, since = va_elbo, ep, 0
                self._save_ckpt("checkpoint_best.pt", ep)
            else:
                since += 1
            if ep % 5 == 0 or improved:
                js = row.get("val_joint_srmse", float("nan"))
                print(f"  ep {ep:3d} | ELBO train {tr_elbo:.3f} val {va_elbo:.3f} | "
                      f"recon {va['recon']:.2f} kl {va['kl']:.2f} act {va['kl_active_dims']} | "
                      f"jointSRMSE {js:.3f} | beta {beta:.2f}{' *' if improved else ''}", flush=True)
            if since >= self.cfg.patience:
                print(f"  early stop @ {ep} (best {best:.3f} @ {best_ep})"); break
        pd.DataFrame(self.history).to_parquet(self.out / "history.parquet", index=False)
        (self.out / "config.json").write_text(json.dumps(
            {"model": asdict(self.m.cfg), "train": asdict(self.cfg),
             "best_val": best, "best_epoch": best_ep}, indent=2))
        return self.history

    def _save_ckpt(self, name, ep):
        ema_model = copy.deepcopy(self.m); self.ema.copy_to(ema_model)
        torch.save({"model_state": self.m.state_dict(),
                    "ema_state": ema_model.state_dict(),
                    "epoch": ep, "model_cfg": asdict(self.m.cfg)}, self.out / name)
