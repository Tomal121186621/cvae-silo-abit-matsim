# Updated VAE — clean population-synthesis CVAE (ACS PUMS 2016 → SILO)

A fresh, simple **conditional VAE** that generates the SILO/MITO synthetic population
(households + persons + dwellings + jobs) for the Baltimore–Washington MSTM region from
**ACS PUMS 2016 5-year** microdata. Rebuilt from scratch to be simple and correct — no
autoregressive decoder, no Set Transformer, no multi-head income model.

## Key design decisions
- **Simple CVAE** (Borysov 2019 style): flat one-hot household vector → MLP encoder → Gaussian
  latent (~16–32 dims, free-bits) → MLP decoder → all softmax heads in one shot. PUMA is the
  only embedded variable; everything else is one-hot. Joints are carried by the latent.
- **Income = binned categorical** (no continuous income head). Continuous dollars are recovered
  at generation by an **empirical within-(PUMA, bin) draw** (the open top bin yields the real
  \$1M+ values). Person↔household income reconciled exactly.
- **Post-hoc constraint enforcement** (not decoder masking): after sampling, `consistency.apply_constraints`
  **overwrites** any age-impossible attribute on the exact within-bin age (e.g. an under-16 "employed" is
  reset to student, an under-62 "retiree" to other), so the exported structural-zero count is 0. This is a
  deterministic post-processing patch, **not** an unreachable-by-construction decoder mask — see the
  limitations note below on why the informative number is the *pre-patch* illegal-combo rate.
- **Self-contained**: all 2016 inputs copied under `inputs/`.

## Layout
```
inputs/        copied raw 2016 ACS PUMS + zoneSystem + coverage + skim + forecasts
vaelib/        importable package (config, analysis, preprocessing, model, train, …)
steps/         numbered runnable scripts, 00 → 07 (first → last)
outputs/       all artifacts (00_raw_analysis … 07_validation)
run_all.py     runs steps 00 → 07 in order
```

## How to run
```bash
pip install -r requirements.txt
python steps/00_analyze_raw_acs.py     # stats + visualizations BEFORE preprocessing (review gate)
python steps/01_preprocess.py
python steps/02_build_targets.py
python steps/03_train.py --smoke        # then without --smoke for the full run
python steps/04_generate.py
python steps/05_workplace.py
python steps/06_silo_export.py
python steps/07_validate.py             # vs held-out 2016 test split
# or: python run_all.py
```

## Data split & validation
- 2016 PUMS split **per-PUMA, household-level, 80/10/10** train/val/test (seeded).
  Train fits; val = early stopping; **test = held-out honest evaluation**.
- Validation is a 12-category journal suite (marginals, joints, association, income tail,
  household structure, spatial, **structural-zeros=0**, **sampling-zeros recovered**,
  memorization, coherence) read against identifiability floors.

## Limitations (disclosed honestly)

- **The "structural zeros = 0" result is a post-patch tautology.** `consistency.apply_constraints`
  deterministically **overwrites** age-impossible attributes, and `count_structural_zeros` is then run on
  the already-patched population, so it is 0 **by construction** — it does not measure model quality. The
  informative number is the **PRE-patch illegal-combo rate**: the share of decoder-sampled persons whose
  raw attributes violate a hard age rule before the patch. Measured on the held-out validation run
  (`steps/07_validate.py`, n = 150k, seed 1; recorded as `8b_prepatch_illegal_combos` in
  `outputs/07_validation/full/results.json`):

  > **PRE-patch: 27,459 illegal combinations = 7.28% of persons.** Breakdown: license<16 6,817;
  > toddler-occupation>age 5 6,648; retiree<62 5,971; non-toddler<6 5,898; employed<16 1,867;
  > spouse<16 258; age-outside-bin 0. All are then overwritten by `apply_constraints`, giving the
  > post-patch 0.

  So the model does produce age-inconsistent draws at a ~7% rate (the softmax heads are conditionally
  independent given the latent and are not age-gated); the exported population is clean only because of the
  post-hoc patch, which is a hard, defensible logical correction — but the honest figure to report is 7.28%,
  not 0.

- **Within-household coupling — couple age-gap is too wide.** Generated spouse/householder age gaps average
  **7.55 years vs 3.69 years in the held-out test** (`6_couple_age_gap` in `results.json`). The single
  shared latent carries most marginals and pairwise joints well but does not pin one household member's
  exact age to another's, so spouse ages spread too far apart. This is a **model bin-level error (+3.3 y)**,
  not the within-bin exact-age draw (~+0.6 y), and is the clearest known limitation of the simple-CVAE
  architecture (an autoregressive or explicit couple-pairing decoder would tighten it, at the cost of the
  simplicity this rebuild was chosen for). Immaterial to the SILO/MITO marginals and household-structure
  targets it feeds, but disclosed for any downstream use that depends on intra-couple age correlation.

Base year: 2016 (USD via ACS ADJINC). Region: 96 MSTM PUMAs across DE/DC/MD/PA/VA/WV.
