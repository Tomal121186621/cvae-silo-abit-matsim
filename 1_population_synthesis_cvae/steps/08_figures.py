#!/usr/bin/env python3
"""STEP 08 — publication-quality figures, ONE METRIC PER FILE (300-dpi PNG + vector PDF).

Training curves + the full 12-category validation framework vs the held-out 2016 test split.
Outputs → outputs/figures/training/  and  outputs/figures/validation/

Usage: python steps/08_figures.py [--tag full] [--n 150000]
"""
from __future__ import annotations
import sys, json, argparse, itertools
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np, pandas as pd, torch
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/code")
import trb_style; trb_style.apply()

from vaelib import config, crosswalks, validate as V
from vaelib.model import CVAE, CVAEConfig
from vaelib.zones import ZoneSampler
from vaelib.generate import generate_population
from vaelib.consistency import count_structural_zeros

ap = argparse.ArgumentParser()
ap.add_argument("--tag", default="full"); ap.add_argument("--n", type=int, default=150000)
ap.add_argument("--device", default="cpu"); args = ap.parse_args()

PRE = config.OUTPUTS_DIR / "01_preprocessed"; TGT = config.OUTPUTS_DIR / "02_targets"
TR = config.OUTPUTS_DIR / "03_training" / args.tag
FT = config.OUTPUTS_DIR / "TRB_figures" / "training"; FT.mkdir(parents=True, exist_ok=True)
FV = config.OUTPUTS_DIR / "TRB_figures" / "validation"; FV.mkdir(parents=True, exist_ok=True)

# TRB/TRR convention: BLUE=simulated (VAE synthetic), OBS=vermillion (real/ACS census).
# The existing script uses BLUE for "ACS test (truth)" and RED for "VAE generated";
# to honour the shared semantics we map the real/census series to OBS (vermillion)
# and the VAE-generated series to SIM (blue). GREEN/PURP are palette accents.
BLUE = trb_style.OBS            # real / ACS test (vermillion)
RED = trb_style.SIM             # VAE generated (blue)
GREEN = trb_style.TARGET        # green accent
PURP = trb_style.PALETTE[4]     # reddish-purple accent
SEQ_CMAP = "cividis"            # colour-blind & grayscale friendly sequential map

_FIGN = itertools.count(1)

def save(fig, d, name):
    """Auto-convert the in-axes title / suptitle into a TRR caption below the figure,
    number figures sequentially, and write BOTH 300-dpi PNG and vector PDF."""
    n = next(_FIGN)
    cap = ""
    supt = getattr(fig, "_suptitle", None)
    if supt is not None and supt.get_text():
        cap = supt.get_text(); supt.set_visible(False)
    else:
        for ax in fig.axes:
            t = ax.get_title()
            if t:
                cap = t; ax.set_title("")
                break
    cap = " ".join(cap.replace("\n", " ").split()).strip()
    caption = f"Figure {n}. {cap}" if cap else f"Figure {n}."
    if not caption.endswith("."):
        caption += "."
    trb_style.save(fig, d / name, caption_text=caption)
    print(f"  {d.name}/{name}.png")

LABELS = {
    "dwellingType": ["SFD", "SFA", "MF2-4", "MF5+", "MH"], "tenure": ["own", "rent"],
    "autos": ["0", "1", "2", "3", "4"], "gender": ["male", "female"],
    "race": ["WhiteNH", "BlackNH", "Hisp", "AsianNH", "Other"],
    "occupation": ["emp", "student", "retiree", "unemp", "toddler", "other"],
    "driversLicense": ["no", "yes"],
    "relationship": ["head", "spouse", "child", "sibling", "parent", "other-rel", "non-rel", "gq"],
}
TITLE = {"dwellingType": "Dwelling type", "tenure": "Tenure", "autos": "Vehicles",
         "income_bin": "Household income bin", "age_bin": "Age (5-yr bins)", "gender": "Gender",
         "race": "Race/ethnicity", "occupation": "Occupation", "driversLicense": "Driver's license",
         "relationship": "Relationship", "pp_income_bin": "Person income bin"}

# ── load model + data, generate validation population from TRAIN only ─────
hh = pd.read_parquet(PRE / "hh.parquet").reset_index(drop=True)
pp = pd.read_parquet(PRE / "pp.parquet")
puma_to_idx = json.loads((TGT / "puma_to_idx.json").read_text())
sp = np.load(TR / "split_idx.npz"); tr_idx, te_idx = sp["train"], sp["test"]
train_hh, test_hh = hh.loc[tr_idx], hh.loc[te_idx]
train_pp = pp[pp["SERIALNO"].isin(set(train_hh["SERIALNO"]))]
test_pp = pp[pp["SERIALNO"].isin(set(test_hh["SERIALNO"]))]
twh, twp = test_hh["WGTP_eff"].to_numpy(), test_pp["PWGTP_eff"].to_numpy()

state = torch.load(TR / "checkpoint_best.pt", map_location=args.device, weights_only=False)
model = CVAE(n_pumas=len(puma_to_idx), cfg=CVAEConfig(**state["model_cfg"]))
model.load_state_dict(state["ema_state"]); model.to(args.device)
zsamp = ZoneSampler(crosswalks.build_zone_table(), rng=np.random.default_rng(7))
print(f"generating {args.n:,} validation HH from train-only...", flush=True)
gen_hh, gen_pp = generate_population(model, train_hh, train_pp, puma_to_idx, zsamp,
                                     n_total=args.n, seed=7, device=args.device)
gwh, gwp = np.ones(len(gen_hh)), np.ones(len(gen_pp))

# ============================ TRAINING FIGURES ============================
print("TRAINING figures:")
h = pd.read_parquet(TR / "history.parquet")
fig, ax = plt.subplots(figsize=(7, 5))
ax.plot(h["epoch"], h["train_total"], color=BLUE, lw=2, label="train")
ax.plot(h["epoch"], h["val_total"], color=RED, lw=2, label="validation")
ax.set_xlabel("epoch"); ax.set_ylabel("ELBO (recon + KL)")
ax.set_title("Training & validation ELBO"); ax.legend(frameon=False)
save(fig, FT, "T1_elbo_curves")

fig, ax = plt.subplots(figsize=(7, 5))
ax.plot(h["epoch"], h["train_recon"], color=BLUE, lw=2, label="train")
ax.plot(h["epoch"], h["val_recon"], color=RED, lw=2, label="validation")
ax.set_xlabel("epoch"); ax.set_ylabel("reconstruction cross-entropy")
ax.set_title("Reconstruction loss"); ax.legend(frameon=False)
save(fig, FT, "T2_reconstruction")

fig, ax = plt.subplots(figsize=(7, 5))
ax.plot(h["epoch"], h["val_kl"], color=PURP, lw=2, label="KL (nats)")
ax.set_xlabel("epoch"); ax.set_ylabel("KL divergence", color=PURP)
ax2 = ax.twinx(); ax2.plot(h["epoch"], h["kl_active_dims"], color=GREEN, lw=2, label="active dims")
ax2.set_ylabel("active latent dims", color=GREEN); ax2.set_ylim(0, model.cfg.latent_dim + 2)
ax2.grid(False); ax.set_title("KL & active latent dimensions (collapse monitor)")
save(fig, FT, "T3_kl_active_dims")

j = h.dropna(subset=["val_joint_srmse"])
fig, ax = plt.subplots(figsize=(7, 5))
ax.plot(j["epoch"], j["val_joint_srmse"], "-o", color=GREEN, ms=4, lw=2)
ax.set_xlabel("epoch"); ax.set_ylabel("validation joint SRMSE (2/3-way)")
ax.set_title("Joint-relationship learning over training")
save(fig, FT, "T4_joint_srmse_trajectory")

fig, ax = plt.subplots(figsize=(7, 5))
ax.plot(h["epoch"], h["beta"], color="#888", lw=2)
ax.set_xlabel("epoch"); ax.set_ylabel("KL weight β"); ax.set_title("KL annealing schedule")
save(fig, FT, "T5_kl_beta_schedule")

# ============================ VALIDATION FIGURES =========================
print("VALIDATION figures:")

def grouped_bar(name, n, base, level):
    ref, refw = (test_hh, twh) if level == "hh" else (test_pp, twp)
    gen, genw = (gen_hh, gwh) if level == "hh" else (gen_pp, gwp)
    p = V._dist(ref[name], refw, n, base); q = V._dist(gen[name], genw, n, base)
    labs = LABELS.get(name, [str(i) for i in range(n)])
    x = np.arange(n); w = 0.4
    fig, ax = plt.subplots(figsize=(max(6, n * 0.5), 5))
    ax.bar(x - w / 2, p * 100, w, color=BLUE, label="ACS test (truth)")
    ax.bar(x + w / 2, q * 100, w, color=RED, label="VAE generated")
    ax.set_xticks(x); ax.set_xticklabels(labs, rotation=45 if max(len(s) for s in labs) > 3 else 0, ha="right")
    ax.set_ylabel("% of population"); ax.set_title(f"{TITLE.get(name, name)}   (TV={V.tv(p,q):.3f})")
    ax.legend(frameon=False)
    save(fig, FV, f"F1_marginal_{level}_{name}")

# F1 — one figure per variable
for nm, n, base in V.HH_VARS:
    grouped_bar(nm, n, base, "hh")
for nm, n, base in V.PP_VARS:
    grouped_bar("pp_income_bin" if nm == "income_bin" else nm, n, base, "pp") if nm != "income_bin" \
        else grouped_bar(nm, n, base, "pp")

# F1 summary — TV per variable vs identifiability floor
mh = V.marginals(gen_hh, test_hh, twh, V.HH_VARS); mp = V.marginals(gen_pp, test_pp, twp, V.PP_VARS)
names = [f"hh:{k}" for k in mh] + [f"pp:{k}" for k in mp]
tvs = [mh[k]["tv"] for k in mh] + [mp[k]["tv"] for k in mp]
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(range(len(names)), tvs, color=BLUE)
ax.axhline(0.03, color=trb_style.NEUTRAL, ls="--", label="0.03 reference")
ax.set_xticks(range(len(names))); ax.set_xticklabels(names, rotation=90)
ax.set_ylabel("Total Variation distance"); ax.set_title("F1 — marginal fidelity (held-out test)")
ax.legend(frameon=False); save(fig, FV, "F1_marginal_TV_summary")

# F8 — joint SRMSE by order
jp = V.joints_by_order(gen_pp, test_pp, twp, V.PP_VARS)
fig, ax = plt.subplots(figsize=(6, 5))
ords = ["1way_mean_srmse", "2way_mean_srmse", "3way_mean_srmse"]
ax.bar(["1-way", "2-way", "3-way"], [jp[o] for o in ords], color=GREEN)
ax.set_ylabel("mean SRMSE"); ax.set_title("F8 — person joint SRMSE by interaction order")
save(fig, FV, "F8_joint_srmse_by_order")

# F8 — worst-pair triptychs (truth / synth / diff)
ncp = {n: c for n, c, _ in V.PP_VARS}; basep = {n: b for n, c, b in V.PP_VARS}
for pairname, _ in jp["worst_pairs"][:3]:
    a, b = pairname.split("×")
    na, nb = ncp[a], ncp[b]
    pa = (pd.to_numeric(test_pp[a]) - basep[a]).clip(0, na - 1).to_numpy()
    pb = (pd.to_numeric(test_pp[b]) - basep[b]).clip(0, nb - 1).to_numpy()
    T = np.histogram2d(pa, pb, bins=[na, nb], weights=twp)[0]; T /= T.sum()
    ga = (pd.to_numeric(gen_pp[a]) - basep[a]).clip(0, na - 1).to_numpy()
    gb = (pd.to_numeric(gen_pp[b]) - basep[b]).clip(0, nb - 1).to_numpy()
    G = np.histogram2d(ga, gb, bins=[na, nb])[0]; G /= G.sum()
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.5))
    vmax = max(T.max(), G.max())
    for axx, M, t in [(axs[0], T, "ACS test"), (axs[1], G, "VAE generated")]:
        im = axx.imshow(M.T, origin="lower", aspect="auto", cmap=SEQ_CMAP, vmin=0, vmax=vmax)
        axx.set_title(t); axx.set_xlabel(TITLE.get(a, a)); axx.set_ylabel(TITLE.get(b, b))
        fig.colorbar(im, ax=axx, fraction=0.046)
    d = G - T; lim = np.abs(d).max()
    im = axs[2].imshow(d.T, origin="lower", aspect="auto", cmap="RdBu_r", vmin=-lim, vmax=lim)
    axs[2].set_title("difference (gen − truth)"); axs[2].set_xlabel(TITLE.get(a, a))
    fig.colorbar(im, ax=axs[2], fraction=0.046)
    fig.suptitle(f"F3 joint: {TITLE.get(a,a)} × {TITLE.get(b,b)}")
    save(fig, FV, f"F3_joint_{a}_x_{b}")

# S3 — Cramér's V matrices (person-level)
def cramers_matrix(df, w):
    vs = [n for n, _, _ in V.PP_VARS]; nc = {n: c for n, c, _ in V.PP_VARS}; bs = {n: b for n, c, b in V.PP_VARS}
    M = np.zeros((len(vs), len(vs)))
    cols = {v: (pd.to_numeric(df[v]) - bs[v]).clip(0, nc[v] - 1).to_numpy() for v in vs}
    for i, a in enumerate(vs):
        for jx, b in enumerate(vs):
            ct = np.histogram2d(cols[a], cols[b], bins=[nc[a], nc[b]], weights=w)[0]
            n = ct.sum();
            if n <= 0: continue
            r, c = ct.sum(1, keepdims=True), ct.sum(0, keepdims=True)
            exp = r * c / n; chi2 = np.nansum((ct - exp) ** 2 / np.where(exp > 0, exp, np.nan))
            k = min(ct.shape) - 1
            M[i, jx] = np.sqrt(chi2 / n / k) if k > 0 else 0
    return np.array(vs), M
vs, Mt = cramers_matrix(test_pp, twp); _, Mg = cramers_matrix(gen_pp, gwp)
for M, t, fn in [(Mt, "ACS test", "S3_cramersV_test"), (Mg, "VAE generated", "S3_cramersV_generated"),
                 (Mg - Mt, "difference (gen − truth)", "S3_cramersV_diff")]:
    fig, ax = plt.subplots(figsize=(7, 6))
    cmap = "RdBu_r" if "diff" in fn else SEQ_CMAP
    lim = np.abs(M).max() if "diff" in fn else 1.0
    im = ax.imshow(M, cmap=cmap, vmin=(-lim if "diff" in fn else 0), vmax=lim)
    ax.set_xticks(range(len(vs))); ax.set_xticklabels(vs, rotation=90)
    ax.set_yticks(range(len(vs))); ax.set_yticklabels(vs)
    ax.set_title(f"S3 — Cramér's V association ({t})"); fig.colorbar(im, fraction=0.046)
    save(fig, FV, fn)

# F5 — income distribution overlay
fig, ax = plt.subplots(figsize=(8, 5))
bins = np.linspace(0, 400_000, 60)
ax.hist(np.clip(test_hh["income_hh"], 0, 4e5), bins=bins, weights=twh, density=True,
        color=BLUE, alpha=0.55, label="ACS test")
ax.hist(np.clip(gen_hh["income_hh"], 0, 4e5), bins=bins, density=True,
        histtype="step", lw=2, color=RED, label="VAE generated")
ax.set_xlabel("household income ($)"); ax.set_ylabel("density")
ax.set_title("F5 — household income distribution ($0–400k)"); ax.legend(frameon=False)
save(fig, FV, "F5_income_distribution")

# F5 — income tail CCDF (log-log)
fig, ax = plt.subplots(figsize=(8, 5))
for d, w, c, l, ls in [(test_hh["income_hh"].to_numpy(), twh, BLUE, "ACS test", "-"),
                       (gen_hh["income_hh"].to_numpy(), gwh, RED, "VAE generated", "--")]:
    o = np.argsort(d); ds, ww = d[o], w[o]; cc = 1 - (np.cumsum(ww) - 0.5 * ww) / ww.sum()
    m = ds > 0; ax.loglog(ds[m], cc[m], ls, color=c, lw=2, label=l)
ax.axvline(3e5, color="gray", ls=":"); ax.axvline(1e6, color="gray", ls=":")
ax.set_xlim(1e4, 3e6); ax.set_xlabel("household income ($)"); ax.set_ylabel("P(income > x)")
ax.set_title("F5 — income tail (log-log survival)"); ax.legend(frameon=False)
save(fig, FV, "F5_income_tail_ccdf")

# F5 — quantile bias
inc = V.income_metrics(gen_hh, test_hh, twh)
fig, ax = plt.subplots(figsize=(6, 5))
ax.bar(["P50", "P95", "P99"], [inc[f"P{q}_bias_pct"] for q in (50, 95, 99)], color=RED)
ax.axhline(0, color="k", lw=0.8); ax.set_ylabel("bias % (gen − test)")
ax.set_title("F5 — income quantile bias"); save(fig, FV, "F5_income_quantile_bias")

# F5 — tail shares
fig, ax = plt.subplots(figsize=(6, 5))
ax.bar(["> $300k\ntest", "> $300k\ngen", "> $1M\ntest", "> $1M\ngen"],
       [inc["share_gt_300k_ref"], inc["share_gt_300k_gen"], inc["share_gt_1m_ref"], inc["share_gt_1m_gen"]],
       color=[BLUE, RED, BLUE, RED]); ax.set_ylabel("% of households")
ax.set_title("F5 — income tail shares"); save(fig, FV, "F5_income_tail_shares")

# F5 — per-PUMA median income scatter
gm = gen_hh.groupby("puma_key")["income_hh"].median()
tm = test_hh.groupby("puma_key").apply(lambda d: V._wq(d["income_hh"].to_numpy(), d["WGTP_eff"].to_numpy(), .5),
                                       include_groups=False)
common = gm.index.intersection(tm.index)
fig, ax = plt.subplots(figsize=(6, 6))
ax.scatter(tm[common] / 1e3, gm[common] / 1e3, s=14, color=PURP, alpha=0.7)
lim = max(tm[common].max(), gm[common].max()) / 1e3
ax.plot([0, lim], [0, lim], "k--", lw=1)
ax.set_xlabel("ACS test median income ($k)"); ax.set_ylabel("VAE median income ($k)")
r = np.corrcoef(tm[common], gm[common])[0, 1]
ax.set_title(f"F5 — per-PUMA median income  (r={r:.3f})"); save(fig, FV, "F5_per_puma_median_income")

# S6 — couple age-gap distribution
def gaps(pp_, hc):
    cp = pp_.loc[pp_["relationship"].isin([0, 1]), [hc, "relationship", "age"]]
    piv = cp.groupby([hc, "relationship"])["age"].first().unstack()
    if 0 not in piv or 1 not in piv: return np.array([])
    return (piv[0] - piv[1]).abs().dropna().to_numpy()
fig, ax = plt.subplots(figsize=(8, 5))
bins = np.arange(0, 41, 2)
ax.hist(gaps(test_pp, "SERIALNO"), bins=bins, density=True, color=BLUE, alpha=0.55, label="ACS test")
ax.hist(gaps(gen_pp, "hh_id"), bins=bins, density=True, histtype="step", lw=2, color=RED, label="VAE generated")
ax.set_xlabel("|householder − spouse| age gap (yrs)"); ax.set_ylabel("density")
ax.set_title(f"S6 — couple age gap (mean: test {V.couple_age_gap(test_pp,'SERIALNO'):.1f}y, "
             f"gen {V.couple_age_gap(gen_pp,'hh_id'):.1f}y)"); ax.legend(frameon=False)
save(fig, FV, "S6_couple_age_gap")

# Spatial — per-PUMA marginal SRMSE
sp_hh = V.per_puma_srmse(gen_hh, test_hh, "WGTP_eff", V.HH_VARS, "hh")
fig, ax = plt.subplots(figsize=(7, 5))
ax.bar(list(sp_hh.keys()), list(sp_hh.values()), color=PURP)
ax.set_ylabel("mean per-PUMA SRMSE"); ax.set_xticklabels(list(sp_hh.keys()), rotation=45, ha="right")
ax.set_title("Spatial — per-PUMA marginal SRMSE (households)"); save(fig, FV, "SP_per_puma_srmse")

# S2 — cell-count parity (sampling zeros)
sz = V.sampling_zeros(gen_pp, train_pp, test_pp)
vars_ = ("age_bin", "occupation", "income_bin", "relationship")
def cells(df):
    k = np.zeros(len(df), np.int64); m = 1
    for v in vars_:
        n = dict((nm, nn) for nm, nn, _ in V.PP_VARS)[v]
        x = pd.to_numeric(df[v]).clip(0, n - 1).to_numpy(); k = k + x * m; m *= n
    return pd.Series(k).value_counts()
ct, cg = cells(test_pp), cells(gen_pp)
allk = ct.index.union(cg.index)
fig, ax = plt.subplots(figsize=(6, 6))
ax.loglog(ct.reindex(allk, fill_value=0) + 1, cg.reindex(allk, fill_value=0) + 1, ".", ms=4, color=GREEN, alpha=0.5)
mx = max(ct.max(), cg.max())
ax.plot([1, mx], [1, mx], "k--", lw=1)
ax.set_xlabel("ACS test cell count (+1)"); ax.set_ylabel("VAE generated cell count (+1)")
ax.set_title(f"S2 — cell-count parity (sampling-zero recovery {sz['recovery_rate']*100:.0f}%)")
save(fig, FV, "S2_cell_count_parity")

# Structural zeros (must be 0)
szc = count_structural_zeros(gen_pp, hh=gen_hh)
rules = [k for k in szc if k != "total"]
fig, ax = plt.subplots(figsize=(9, 5))
ax.bar(rules, [szc[k] for k in rules], color=RED)
ax.set_ylabel("violations (count)"); ax.set_ylim(0, 1)
ax.set_xticklabels(rules, rotation=45, ha="right")
ax.set_title(f"Structural zeros — total = {szc['total']} (must be 0)"); save(fig, FV, "Z_structural_zeros")

# Floors — marginal SRMSE vs identifiability floor
te = test_hh.sample(frac=1.0, random_state=0); half = len(te) // 2
fnames, gen_s, flr = [], [], []
for nm, n, base in V.HH_VARS:
    a, b = te.iloc[:half], te.iloc[half:]
    fl = V.srmse(V._dist(a[nm], a["WGTP_eff"].to_numpy(), n, base),
                 V._dist(b[nm], b["WGTP_eff"].to_numpy(), n, base))
    gs = V.srmse(V._dist(test_hh[nm], twh, n, base), V._dist(gen_hh[nm], gwh, n, base))
    fnames.append(nm); gen_s.append(gs); flr.append(fl)
x = np.arange(len(fnames)); w = 0.4
fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(x - w / 2, gen_s, w, color=RED, label="VAE SRMSE")
ax.bar(x + w / 2, flr, w, color="#999", label="identifiability floor")
ax.set_xticks(x); ax.set_xticklabels(fnames, rotation=45, ha="right")
ax.set_ylabel("SRMSE"); ax.set_title("Identifiability floors (HH marginals)"); ax.legend(frameon=False)
save(fig, FV, "F12_srmse_vs_floor")

# Memorization
mem = V.memorization(gen_pp, train_pp)
fig, ax = plt.subplots(figsize=(5, 5))
ax.bar(["in train", "novel"], [mem["frac_gen_types_in_train"] * 100,
       (1 - mem["frac_gen_types_in_train"]) * 100], color=[BLUE, GREEN])
ax.set_ylabel("% of generated person-types"); ax.set_title("Memorization / diversity")
save(fig, FV, "M_memorization")

print(f"\nDONE — figures in {FT} and {FV}")
print(f"  training: {len(list(FT.glob('*.png')))} | validation: {len(list(FV.glob('*.png')))}")
