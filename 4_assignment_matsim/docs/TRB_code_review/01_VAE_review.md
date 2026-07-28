# TRB Peer Review — Updated VAE (CVAE synthetic population)

**Scope reviewed:** `Updated VAE/vaelib/{model,train,generate,validate,income_bins,config,dataset,consistency,preprocessing}.py`, `steps/{03_train,04_generate,07_validate}.py`, `README.md`, and `outputs/07_validation/full/results.json`.
**Verdict:** The VAE core (loss, reparameterization, KL/free-bits, train/test discipline) is **mathematically correct and honestly split**. There are **no CRITICAL correctness bugs** in the learning code. The defensible findings are (a) one **methodology claim that the code does not implement** (masked constrained decoding), (b) a **tautological validation category**, and (c) several **overstated fidelity claims** that the model's own numbers contradict. Details below with exact `file:line`.

---

## MAJOR

### M1 — "Constrained decoding masks make impossible classes unreachable" is not implemented (hallucinated method)
- **Where claimed:** `README.md:15` ("**Constrained decoding** masks make impossible classes unreachable → structural zeros = 0"); echoed by `vaelib/validate.py:1-5` (category "structural zeros (=0)").
- **What the code does:** `CVAE.decode`/`CVAE.sample` (`vaelib/model.py:117-213`) apply **no logit masking** — grep confirms the only masks in `model.py` are the person-**padding** mask (`pp_mask`) and numeric `clamp`s. Structural zeros are eliminated **after** sampling by deterministic overwrites in `vaelib/consistency.py:16-38` (`apply_constraints`: e.g. `occ[under6]=5`, `occ[(age<62)&(occ==3)]=6`, `rel[(rel==1)&(age<16)]=2`) and `enforce_one_householder` (`consistency.py:41-50`).
- **Why it's wrong:** "Masking" and "post-hoc overwrite" are not equivalent. Masking renormalizes the decoder distribution over *legal* classes; overwriting *reassigns* an already-sampled illegal draw to a fixed class, which **biases the conditional distribution** (every illegal draw is funneled to one deterministic category, not redistributed by the model's own probabilities). The paper/README should describe the actual mechanism (rule-based post-processing) rather than claim constrained decoding.
- **Fix:** Either (i) implement true masking — add `-inf` to structurally-impossible logits inside `decode`/`sample` before softmax, keyed on the conditioning available at decode (note: exact age is drawn *after* sampling, so age-threshold rules cannot be masked without restructuring), or (ii) correct the wording in README/paper to "deterministic post-hoc constraint enforcement."

### M2 — Structural-zeros validation (category 8) is tautological / circular
- **Where:** `steps/07_validate.py:65` calls `count_structural_zeros(gen_pp, ...)` on a `gen_pp` that `generate_population` already ran through `apply_constraints` + `enforce_one_householder` (`vaelib/generate.py:89-90`). `count_structural_zeros` (`consistency.py:53-77`) checks the **same thresholds** (`age<16`, `age<62`, `occ==5 & age>=6`, one householder) that `apply_constraints` just enforced with identical constants.
- **Why it's wrong:** The reported "STRUCTURAL ZEROS: 0 PASS" (`results.json` `8_structural_zeros.total=0`, printed at `07_validate.py:119`) is guaranteed by construction and carries **no information about model quality** — it validates that a deterministic patch executed, not that the generator learned anything. Presenting it as one of "12 validation categories" inflates the apparent rigor.
- **Fix:** Report structural-zero rate **before** `apply_constraints` (i.e., how often the raw decoder produces illegal combinations) — that is the informative number. Keep the post-constraint check only as an internal assertion.

### M3 — Couple age-gap is 2× reality; the "household structure" category is a fidelity failure, not a pass
- **Where:** `results.json` `6_couple_age_gap`: **gen = 7.55 yr vs test = 3.69 yr**; metric computed in `validate.py:97-104`, printed `07_validate.py:118`.
- **Why it matters:** Generated spouses are on average **twice as far apart in age** as real couples. This is the expected consequence of decoding all persons in a household **independently** from a shared latent + slot one-hot (`model.py:117-125`) with **no pairwise age coupling** — the model captures per-slot marginals but not the householder↔spouse age correlation. The project memory already flags "couple-age-gap is the trade-off," but the README/deck should not present S6 as passing. This is a legitimate limitation to disclose in the paper (it propagates into any downstream marriage/aging dynamics).
- **Fix (disclosure, not necessarily code):** State the limitation explicitly. If a fix is wanted, add a spouse-age-gap coupling term or a post-hoc age-matching pass for relationship∈{0,1}.

---

## MINOR

### m1 — "All marginals < 5%" is true for TV but income is a genuine (small) miss vs its own noise floor
- `results.json`: `income_bin` marginal **SRMSE 0.093 vs identifiability floor 0.0596** (`12_identifiability_floor_hh.income_bin`), and **TV 0.033 > the 0.03 reference line** drawn in `07_validate.py:90`. It is the **only** marginal that exceeds its half-test-split noise floor, i.e. the one distribution the model measurably fails to reproduce. The "<5%" headline (CLAUDE.md) holds on TV, but the paper should not imply income is at floor.

### m2 — Person-level "empirical within-(PUMA,bin) income draw" is largely overwritten by reconciliation
- `README.md:13-14` claims continuous person incomes come from an empirical within-bin draw. In `generate.py:85-93`, the drawn person incomes are then **rescaled** by `_reconcile` → `reconcile_pp_to_hh` (`income_bins.py:66-94`) to sum exactly to the independently-drawn HH income. After scaling, the person dollar values are no longer the empirical draws. Only the **categorical `income_bin`** is genuinely modeled; the person dollars are a rescaled artifact. State this precisely.

### m3 — "Person↔household income reconciled exactly" is 99.98%, not 100%, due to negative-income households
- `results.json` `11_coherence.sigma_income_exact_pct = 99.98`. Cause: when the HH within-bin draw yields `hh_total <= 0` (bin 0 includes negatives, `config.py:82-86`), `reconcile_pp_to_hh` returns all-zero person incomes (`income_bins.py:74-75`) while `gen_hh.income_hh` stays negative → Σperson ≠ HH for those rows. Minor, but the README wording "reconciled exactly" (`README.md:14`) is slightly overstated.

### m4 — Memorization metric conflates fidelity with memorization
- `validate.py:141-147` hashes only 7 low-cardinality person vars; `frac_gen_types_in_train = 0.595` (`results.json`). With that few categorical dims the type space is small, so high train-overlap is **expected and desirable**, not evidence of memorization. The metric cannot distinguish "learned the common types" from "copied records." Consider a nearest-neighbour / full-record distance instead, or drop the claim.

### m5 — Identifiability floor is computed only for 4 HH vars and by halving the 10% test set
- `07_validate.py:70-79`: floor uses `test_hh` split in half and **only `V.HH_VARS`** — no person-variable floor, and the small subsample (≈5% of data each half) inflates the floor via sampling noise, flattering the model. Report person-var floors too and/or bootstrap the floor.

### m6 — Model-selection "β=1 ELBO" includes the free-bits-floored KL, so selection is effectively recon-only
- `train.py:168` selects on `va_elbo = recon + kl`, described (`train.py:166-167`) as "the β=1 ELBO." But `kl` is the **free-bits-clamped** quantity (`model.py:146`, `clamp_min(0.5).sum()` ≈ 24×0.5 = 12 nats floor), not the true KL. Once dims sit near the floor, `kl` is ~constant and early-stopping tracks reconstruction only. Not a bug, but the label "ELBO" is imprecise for a reproducibility appendix.

---

## What's correct / solid (credit where due)

- **KL divergence formula is correct:** `model.py:144`, `-0.5*(1+logvar-mu²-exp(logvar))` = analytic KL(N(μ,σ²)‖N(0,I)) per dim, always ≥ 0.
- **Reparameterization is correct:** `model.py:130`, `z = mu + randn*(0.5*logvar).exp()` uses std = exp(½·logvar) = √var. `logvar.clamp(-8,8)` (`model.py:115`) is a sane numerical guard.
- **Free-bits anti-collapse is correctly implemented** as a per-dim floor on the batch-mean KL (`model.py:144-146`); gradient correctly stops when a dim is below floor. Active-dim monitor and `LATENT COLLAPSE` verdict (`diagnostics.py:22-31`) are reasonable.
- **Weighting is consistent and per-capita:** recon and KL are both survey-weighted with the same normalized `w` (`model.py:132-146`); generated pop is unit-weighted and compared against weighted reference marginals (`validate.py:37-43`) — dimensionally correct.
- **Train/test discipline is honest — no obvious leakage:** the per-PUMA HH-level split is drawn once (`dataset.py:53-62`), saved (`03_train.py:47`), and reloaded in validation (`07_validate.py:34-38`); the validation population is generated from **train-only** conditioning **and** a train-only within-bin income sampler (`07_validate.py:46-50`), then scored against the held-out **test** split. `SERIALNO`-based person filtering keeps households intact across the split.
- **β-annealing, AdamW, grad-clipping, EMA** are all present and standard (`train.py:143-144, 163, 104-115`); inference correctly loads EMA weights (`04_generate.py:35`, `07_validate.py:44`).
- **Base/one-hot offset bookkeeping is consistent** across preprocess → generate → validate (base added back at `generate.py:56,65`, subtracted at `validate.py:24-27`); income_bin correctly kept 0-indexed everywhere.
- **Sampling matches training semantics:** decoder is shared across person slots via slot one-hot (`model.py:121-123`); persons are ordered householder-first at both training (`dataset.py:37-40`) and generation (`generate.py:60-63`), so slot conditioning is coherent.
- **Reconciliation is a proper largest-remainder integer allocation** (`income_bins.py:81-94`) — rank-preserving and exact when target > 0.

---

## Bottom line for the paper
The learning machinery is sound and the held-out evaluation is set up honestly (this is better than most population-synthesis code). The required edits are **claims, not code**: (1) stop calling the post-hoc rule enforcement "constrained decoding masks" (M1); (2) drop or reframe the tautological structural-zeros "pass" (M2); (3) disclose the couple age-gap failure (M3, 7.6 vs 3.7 yr) and the income marginal / person-income-draw caveats (m1–m3). None of these invalidate the synthetic population for the SILO/congestion-pricing pipeline, but each is a place a careful TRB reviewer will otherwise catch an overstatement.
