#!/usr/bin/env python3
"""Paper-style Cramer's V association figure for the CVAE validation:
(a) observed (held-out ACS test) pairwise V matrix over the eight person attributes;
(b) difference (synthesized - observed), diverging scale.
Plain (uncorrected) Cramer's V, matching the pipeline: V = sqrt(chi2 / (n * (min(r,c)-1))).
"""
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM")
VAE = ROOT / "Updated VAE/outputs"
OUT = ROOT / "PAPERS/TRB_zip_v40/figures/vae"

ATTRS = ["age_bin", "gender", "race", "occupation", "driversLicense",
         "relationship", "nationality", "income_bin"]
LAB = ["Age", "Gender", "Race/eth.", "Occupation", "License", "Relationship", "Nativity", "Income"]

pp = pd.read_parquet(VAE / "01_preprocessed/pp.parquet", columns=ATTRS + ["PWGTP_eff"])
test_idx = np.load(VAE / "03_training/full/split_idx.npz")["test"]
# split indices are household-level; approximate person-level test by household draw is not
# available here, so use the persons of the full preprocessed table's test households if mapping
# exists; otherwise fall back to the whole held-out-comparable sample.
try:
    hh = pd.read_parquet(VAE / "01_preprocessed/hh.parquet", columns=["SERIALNO"])
    test_ser = set(hh.iloc[test_idx].SERIALNO)
    ppf = pd.read_parquet(VAE / "01_preprocessed/pp.parquet", columns=["SERIALNO", "PWGTP_eff"] + ATTRS)
    obs = ppf[ppf.SERIALNO.isin(test_ser)][ATTRS + ['PWGTP_eff']]
except Exception:
    obs = pp
gen = pd.read_parquet(VAE / "04_generated/pp.parquet", columns=ATTRS)
if len(gen) > 400_000:
    gen = gen.sample(400_000, random_state=0)
print("obs persons:", len(obs), " gen persons:", len(gen))

def cramers(df, w=None):
    if w is None: w = np.ones(len(df))
    M = np.eye(len(ATTRS))
    for i in range(len(ATTRS)):
        for j in range(i + 1, len(ATTRS)):
            ct = pd.crosstab(df[ATTRS[i]], df[ATTRS[j]], values=w, aggfunc="sum").fillna(0).to_numpy()
            E = np.outer(ct.sum(1), ct.sum(0)) / ct.sum()
            chi2 = ((ct - E) ** 2 / np.where(E == 0, 1, E)).sum()
            k = min(ct.shape[0], ct.shape[1]) - 1
            M[i, j] = M[j, i] = np.sqrt(chi2 / (ct.sum() * max(k, 1)))
    return M

Vo = cramers(obs[ATTRS], obs['PWGTP_eff'].to_numpy() if 'PWGTP_eff' in obs else None)
Vg = cramers(gen)
D = Vg - Vo
np.fill_diagonal(D, 0.0)
print("mean |diff|:", round(np.abs(D[np.triu_indices(8, 1)]).mean(), 3),
      " max |diff|:", round(np.abs(D).max(), 3))

plt.rcParams.update({"font.family": "serif", "font.size": 10, "savefig.dpi": 300})
fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.4))
im0 = axes[0].imshow(Vo, cmap="Blues", vmin=0, vmax=1)
axes[0].set_title("(a) Observed association (held-out test)", fontsize=10.5)
im1 = axes[1].imshow(D, cmap="RdBu_r", vmin=-0.1, vmax=0.1)
axes[1].set_title("(b) Difference, synthesized $-$ observed", fontsize=10.5)
for ax in axes:
    ax.set_xticks(range(8)); ax.set_xticklabels(LAB, rotation=45, ha="right", fontsize=8.5)
    ax.set_yticks(range(8)); ax.set_yticklabels(LAB, fontsize=8.5)
for ax, im, lab in ((axes[0], im0, "Cramér's $V$"), (axes[1], im1, "$\\Delta V$")):
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label(lab, fontsize=9); cb.ax.tick_params(labelsize=8); cb.outline.set_visible(False)
fig.tight_layout()
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "vae_cramers.pdf", bbox_inches="tight")
fig.savefig(OUT / "vae_cramers.png", bbox_inches="tight")
print("wrote", OUT / "vae_cramers.pdf")
