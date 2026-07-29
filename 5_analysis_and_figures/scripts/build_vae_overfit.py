#!/usr/bin/env python3
"""CVAE generalization figure: train vs held-out ELBO (no over-fitting) and
active latent dimensions (no posterior collapse). Reads the canonical "full"
training history used for the other CVAE paper figures.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_style as ps
ps.apply()
import matplotlib.pyplot as plt

HIST = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"
            "/Updated VAE/outputs/03_training/full/history.parquet")
OUT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"
           "/Paper Figures Final/figures/vae/vae_overfit")


def main():
    h = pd.read_parquet(HIST).sort_values("epoch")
    ep = h["epoch"].to_numpy()
    anneal = int(h.loc[h["beta"] >= 1.0, "epoch"].min())          # beta reaches 1
    gap = float(h["val_total"].iloc[-1] - h["train_total"].iloc[-1])

    fig, ax1 = plt.subplots(figsize=(ps.TEXTWIDTH_IN * 0.60, ps.TEXTWIDTH_IN * 0.40))

    ax1.axvspan(ep.min(), anneal, color="0.90", zorder=0)
    ax1.plot(ep, h["train_total"], color=ps.SIM, lw=1.8, label="Training")
    ax1.plot(ep, h["val_total"], color=ps.OBS, lw=1.8, ls="--", label="Held-out")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("ELBO (recon. + KL)")
    ax1.set_xlim(ep.min(), ep.max())
    ax1.set_ylim(18, 30)
    ax1.text(anneal + 3, 28.6, "$\\beta$ annealing", fontsize=7.5, color="0.35")
    # gap annotation removed (2026-07-29): curves speak for themselves
    ax1.legend(frameon=False, loc="upper right", fontsize=8)

    fig.tight_layout()
    fig.subplots_adjust(wspace=0.32)
    ps.save(fig, str(OUT))
    print(f"final train {h.train_total.iloc[-1]:.2f} / val {h.val_total.iloc[-1]:.2f} "
          f"/ gap {gap:.3f} / active {int(h.kl_active_dims.iloc[-1])} / anneal@{anneal}")


if __name__ == "__main__":
    main()
