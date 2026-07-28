#!/usr/bin/env python3
"""MATSim co-evolutionary convergence figure for the loaded base run: average
executed plan score by iteration, with the best/worst plan-memory envelope. Reads
the reported base run's scorestats so the figure ties to the validated network.
"""
import sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_style as ps
ps.apply()
import matplotlib.pyplot as plt

SC = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
          "/scenarios/02_i695_congestion_pricing/runs/loaded_base_v4/scorestats.csv")
OUT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"
           "/Paper Figures Final/figures/matsim/matsim_convergence")


def main():
    d = pd.read_csv(SC, sep=";").sort_values("iteration")
    it = d["iteration"].to_numpy()

    fig, ax = plt.subplots(figsize=(ps.TEXTWIDTH_IN * 0.60, ps.TEXTWIDTH_IN * 0.40))

    ax.fill_between(it, d["avg_worst"], d["avg_best"], color=ps.SIM, alpha=0.12,
                    lw=0, label="best/worst plan envelope")
    ax.plot(it, d["avg_best"], color=ps.NEUTRAL, lw=0.8, ls=":")
    ax.plot(it, d["avg_worst"], color=ps.NEUTRAL, lw=0.8, ls=":")
    ax.plot(it, d["avg_executed"], color=ps.SIM, lw=1.9, label="average executed score")

    ax.set_xlabel("Iteration")
    ax.set_ylabel("Plan score")
    ax.set_xlim(it.min(), it.max())
    ax.axvspan(it.min(), 8, color="0.92", zorder=0)
    ax.text(3.9, 0.2, "burn-in", fontsize=7.5, color="0.4", ha="center")
    ax.legend(frameon=False, loc="center right", fontsize=7.5)

    fig.tight_layout()
    ps.save(fig, str(OUT))
    print(f"iters {it.min()}-{it.max()} | executed {d.avg_executed.iloc[0]:.2f} -> "
          f"{d.avg_executed.iloc[-1]:.2f} | last-5 range "
          f"{d.avg_executed.iloc[-5:].max()-d.avg_executed.iloc[-5:].min():.2f}")


if __name__ == "__main__":
    main()
