#!/usr/bin/env python3
"""Composite SILO land-use validation figure for the TRB paper.

ONE figure, 8 uniform grouped-bar panels: SILO 2023 (Model, blue) vs ACS 2023
Maryland PUMS (Observed, orange). Household vars first (hhSize, autos, dwellingType,
hh_inc9), then person vars (age_bin, gender, occ_silo, race4). Shares + TV distances
are computed from the real SILO output and ACS PUMS through valib's own loaders — no
values are hand-entered here.

Style is the paper-wide paper_style module (matches figures/vae/vae_pp_marginals.png).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

# --- paper style (this figure's look) ---
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_style as ps
ps.apply()
import matplotlib.pyplot as plt

# --- reuse the SILO validation library + the MD-2023 ACS loader verbatim ---
SILO_CODE = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated SILO/code")
sys.path.insert(0, str(SILO_CODE))
import valib as m
m.SCEN = Path("/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test"
              "/scenOutput/updated_vae_calib5/microData")
from make_perattr_md2023_trb import load_acs_md   # ACS 2023 MD PUMS -> validation schema

YEAR = 2023
OUT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"
           "/Paper Figures Final/figures/silo/silo_md_2023")

# panel order: 4 HH then 4 PP; titles are short variable names (TV appended per panel)
PANELS = [
    ("hh", "hhSize",       "Household size"),
    ("hh", "autos",        "Autos per HH"),
    ("hh", "dwellingType", "Dwelling type"),
    ("hh", "hh_inc9",      "Household income"),
    ("pp", "age_bin",      "Age band"),
    ("pp", "gender",       "Gender"),
    ("pp", "occ_silo",     "Occupation"),
    ("pp", "race4",        "Race / ethnicity"),
]


def shares(vals, w, cats):
    """Weighted share vector over the ordered category list (reuses valib._wdist)."""
    return m._wdist(vals, w, cats)


def main():
    print("loading ACS 2023 MD PUMS ...", flush=True)
    rh, rp = load_acs_md(YEAR)
    print("loading SILO 2023 output (calib5) ...", flush=True)
    sh, sp = m.load_silo_year(YEAR)
    sh = sh[sh.state == "MD"]; sp = sp[sp.state == "MD"]
    frames = {"hh": (sh, rh), "pp": (sp, rp)}

    fig, axes = plt.subplots(4, 2, figsize=(ps.TEXTWIDTH_IN, 9.2))
    axes = axes.ravel()
    tvs = {}

    for i, (kind, var, name) in enumerate(PANELS):
        ax = axes[i]
        smodel, robs = frames[kind]
        cats, labels = m.VAR_CATEGORIES[var]
        sp_share = shares(smodel[var], smodel.w, cats)   # SILO / Model
        rp_share = shares(robs[var], robs.w, cats)       # ACS  / Observed
        tv = 0.5 * float(np.abs(sp_share - rp_share).sum())
        tvs[var] = tv

        sparse = 4 if var == "age_bin" else None         # thin ticks only for the 18-bin age panel
        ps.grouped_bar(
            ax, labels,
            [(ps.LAB_OBS, rp_share * 100, ps.OBS),
             (ps.LAB_SIM, sp_share * 100, ps.SIM)],
            title=f"{name}  (TV={tv:.3f})",
            sparse=sparse,
        )
        ps.panel_letter(ax, i)

    handles, labs = axes[0].get_legend_handles_labels()
    ps.shared_legend(fig, handles, labs, ncol=2, y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.975))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    ps.save(fig, str(OUT))
    print("\nTV distances:")
    for _, var, name in PANELS:
        print(f"  {name:18s} ({var:12s}): TV = {tvs[var]:.4f}")


if __name__ == "__main__":
    main()
