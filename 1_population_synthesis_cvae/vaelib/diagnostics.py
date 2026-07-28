"""Training dashboards + automated overfit/underfit verdict."""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def fit_verdict(h: pd.DataFrame) -> dict:
    """Heuristic verdict. overfit = val rising while train falls / best far behind;
    underfit = still falling at end (no plateau) or latent collapse."""
    n = len(h)
    tail = h.tail(max(5, n // 5))
    val_slope = np.polyfit(tail["epoch"], tail["val_total"], 1)[0] if len(tail) > 1 else 0.0
    train_slope = np.polyfit(tail["epoch"], tail["train_total"], 1)[0] if len(tail) > 1 else 0.0
    best_ep = int(h["val_total"].idxmin()); since_best = n - 1 - best_ep
    gap = float(h["val_total"].iloc[-1] - h["train_total"].iloc[-1])
    active = float(h["kl_active_dims"].iloc[-1])
    collapse = active < 2
    overfit = (val_slope > 1e-3 and train_slope < -1e-3) or since_best > 0.4 * n
    underfit = (val_slope < -5e-3) or collapse
    verdict = ("LATENT COLLAPSE" if collapse else
               "OVERFITTING" if overfit else
               "UNDERFITTING (still improving / not plateaued)" if underfit else
               "GOOD FIT")
    return {"verdict": verdict, "val_slope_recent": float(val_slope),
            "train_slope_recent": float(train_slope), "gap_final": gap,
            "best_epoch": best_ep, "since_best": int(since_best),
            "kl_active_dims": active, "collapse": bool(collapse)}


def plot_dashboard(h: pd.DataFrame, out_path):
    plt.rcParams.update({"figure.dpi": 110, "font.size": 9, "axes.grid": True, "grid.alpha": .3})
    fig, ax = plt.subplots(2, 2, figsize=(14, 9))
    ax[0, 0].plot(h["epoch"], h["train_total"], label="train")
    ax[0, 0].plot(h["epoch"], h["val_total"], label="val")
    ax[0, 0].set_title("Total loss (train vs val)", fontweight="bold"); ax[0, 0].legend()
    ax[0, 1].plot(h["epoch"], h["train_recon"], label="train recon")
    ax[0, 1].plot(h["epoch"], h["val_recon"], label="val recon")
    ax[0, 1].set_title("Reconstruction (CE)", fontweight="bold"); ax[0, 1].legend()
    axk = ax[1, 0]; axk.plot(h["epoch"], h["val_kl"], color="#4C72B0", label="val KL")
    axk.set_ylabel("KL"); axk.legend(loc="upper left")
    axa = axk.twinx(); axa.plot(h["epoch"], h["kl_active_dims"], color="#C44E52", label="active dims")
    axa.set_ylabel("active dims"); axa.legend(loc="upper right")
    axk.set_title("KL & active latent dims (collapse monitor)", fontweight="bold")
    j = h.dropna(subset=["val_joint_srmse"]) if "val_joint_srmse" in h else h.iloc[0:0]
    if len(j):
        ax[1, 1].plot(j["epoch"], j["val_joint_srmse"], "-o", color="#55A868")
    ax[1, 1].set_title("Validation joint SRMSE (are joints learned?)", fontweight="bold")
    ax[1, 1].set_xlabel("epoch")
    v = fit_verdict(h)
    fig.suptitle(f"Training dashboard — verdict: {v['verdict']}  "
                 f"(active dims={v['kl_active_dims']:.0f}, gap={v['gap_final']:.2f})",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96]); fig.savefig(out_path); plt.close(fig)
    return v
