#!/usr/bin/env python3
"""STEP 03 — train the simple CVAE. 80/10/10 per-PUMA HH-level split; CE+KL(free-bits)
[+ optional marginal-JSD]; dashboards + overfit/underfit verdict.

Usage:
  python steps/03_train.py [--smoke] [--epochs N] [--w-marginal W] [--latent D] [--tag NAME]
"""
from __future__ import annotations
import sys, json, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from vaelib import config, targets as T
from vaelib.dataset import build_arrays, stratified_split
from vaelib.model import CVAE, CVAEConfig
from vaelib.train import Trainer, TrainConfig, build_marginal_tensors
from vaelib.diagnostics import plot_dashboard

ap = argparse.ArgumentParser()
ap.add_argument("--smoke", action="store_true")
ap.add_argument("--epochs", type=int, default=300)
ap.add_argument("--w-marginal", type=float, default=0.0)
ap.add_argument("--latent", type=int, default=24)
ap.add_argument("--hidden", type=int, default=256)
ap.add_argument("--dec-depth", type=int, default=2)
ap.add_argument("--enc-depth", type=int, default=2)
ap.add_argument("--free-bits", type=float, default=0.5)
ap.add_argument("--beta", type=float, default=1.0, help="kl_max_beta")
ap.add_argument("--tag", default="full")
ap.add_argument("--device", default="cpu")
args = ap.parse_args()

PRE = config.OUTPUTS_DIR / "01_preprocessed"
TGT = config.OUTPUTS_DIR / "02_targets"
tag = "smoke" if args.smoke else args.tag
OUT = config.OUTPUTS_DIR / "03_training" / tag
OUT.mkdir(parents=True, exist_ok=True)

hh = pd.read_parquet(PRE / "hh.parquet"); pp = pd.read_parquet(PRE / "pp.parquet")
puma_to_idx = json.loads((TGT / "puma_to_idx.json").read_text())
puma_targets = T.load_targets(TGT / "puma_targets.json")

arrays = build_arrays(hh, pp, puma_to_idx)
tr, va, te = stratified_split(hh, fracs=(0.8, 0.1, 0.1), seed=0)
np.savez(OUT / "split_idx.npz", train=tr, val=va, test=te)
# split integrity check
n_pumas_each = [hh.iloc[ix]["puma_key"].nunique() for ix in (tr, va, te)]
print(f"split: train {len(tr):,} / val {len(va):,} / test {len(te):,} HH | "
      f"PUMAs per split: {n_pumas_each}")

mcfg = CVAEConfig(latent_dim=args.latent, w_marginal=args.w_marginal, hidden_dim=args.hidden,
                  dec_depth=args.dec_depth, enc_depth=args.enc_depth, free_bits=args.free_bits)
model = CVAE(n_pumas=len(puma_to_idx), cfg=mcfg)
n_params = sum(p.numel() for p in model.parameters())
print(f"model params: {n_params:,} | latent={mcfg.latent_dim} | w_marginal={mcfg.w_marginal}")

marg = build_marginal_tensors(puma_targets, puma_to_idx, args.device) if args.w_marginal > 0 else None
tcfg = TrainConfig(max_epochs=2 if args.smoke else args.epochs,
                   kl_anneal_epochs=2 if args.smoke else 30, kl_max_beta=args.beta,
                   patience=2 if args.smoke else 25, device=args.device,
                   joint_eval_every=1 if args.smoke else 5)
trainer = Trainer(model, arrays, tr, va, tcfg, OUT, marg=marg)
history = pd.DataFrame(trainer.train())

verdict = plot_dashboard(history, OUT / "dashboard.png")
(OUT / "fit_verdict.json").write_text(json.dumps(verdict, indent=2))
print(f"\nVERDICT: {verdict['verdict']}")
print(f"  active dims={verdict['kl_active_dims']:.0f}, gap={verdict['gap_final']:.3f}, "
      f"best_epoch={verdict['best_epoch']}")
if "val_joint_srmse" in history:
    last = history.dropna(subset=["val_joint_srmse"]).tail(1)
    if len(last): print(f"  final val joint-SRMSE: {last['val_joint_srmse'].iloc[0]:.3f}")
print(f"saved → {OUT}")
