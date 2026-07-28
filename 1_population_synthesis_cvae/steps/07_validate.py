#!/usr/bin/env python3
"""STEP 07 — comprehensive validation vs the held-out 2016 TEST split.

Generates a validation population from TRAIN-only (honest: conditioning + within-bin income
sampler use train records, never test), then scores the 12-category suite against TEST.
Outputs → outputs/07_validation/{results.json, summary.png}
"""
from __future__ import annotations
import sys, json, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np, pandas as pd, torch
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from vaelib import config, crosswalks, validate as V
from vaelib.model import CVAE, CVAEConfig
from vaelib.zones import ZoneSampler
from vaelib.generate import generate_population
from vaelib.consistency import count_structural_zeros

ap = argparse.ArgumentParser()
ap.add_argument("--tag", default="full")
ap.add_argument("--n", type=int, default=150_000, help="validation population size")
ap.add_argument("--device", default="cpu")
args = ap.parse_args()

PRE = config.OUTPUTS_DIR / "01_preprocessed"; TGT = config.OUTPUTS_DIR / "02_targets"
TR = config.OUTPUTS_DIR / "03_training" / args.tag
OUT = config.OUTPUTS_DIR / "07_validation" / args.tag; OUT.mkdir(parents=True, exist_ok=True)

hh = pd.read_parquet(PRE / "hh.parquet").reset_index(drop=True)
pp = pd.read_parquet(PRE / "pp.parquet")
puma_to_idx = json.loads((TGT / "puma_to_idx.json").read_text())
sp = np.load(TR / "split_idx.npz")
tr_idx, te_idx = sp["train"], sp["test"]
train_hh = hh.loc[tr_idx]; test_hh = hh.loc[te_idx]
train_ser = set(train_hh["SERIALNO"]); test_ser = set(test_hh["SERIALNO"])
train_pp = pp[pp["SERIALNO"].isin(train_ser)]; test_pp = pp[pp["SERIALNO"].isin(test_ser)]
print(f"train {len(train_hh):,} HH / test {len(test_hh):,} HH", flush=True)

# model (EMA)
state = torch.load(TR / "checkpoint_best.pt", map_location=args.device, weights_only=False)
model = CVAE(n_pumas=len(puma_to_idx), cfg=CVAEConfig(**state["model_cfg"]))
model.load_state_dict(state["ema_state"]); model.to(args.device)

# generate validation population from TRAIN ONLY
zsamp = ZoneSampler(crosswalks.build_zone_table(), rng=np.random.default_rng(1))
print(f"generating {args.n:,} validation households from train-only...", flush=True)
gen_hh, gen_pp = generate_population(model, train_hh, train_pp, puma_to_idx, zsamp,
                                     n_total=args.n, seed=1, device=args.device)

# ── run the 12-category suite ────────────────────────────────────────────
res = {}
res["1_totals"] = {"gen_hh": len(gen_hh), "gen_pp": len(gen_pp),
                   "persons_per_hh_gen": len(gen_pp) / len(gen_hh),
                   "persons_per_hh_test": len(test_pp) / len(test_hh)}
res["2_marginals_hh"] = V.marginals(gen_hh, test_hh, test_hh["WGTP_eff"].to_numpy(), V.HH_VARS)
res["2_marginals_pp"] = V.marginals(gen_pp, test_pp, test_pp["PWGTP_eff"].to_numpy(), V.PP_VARS)
res["3_joints_pp"] = V.joints_by_order(gen_pp, test_pp, test_pp["PWGTP_eff"].to_numpy(), V.PP_VARS)
res["3_joints_hh"] = V.joints_by_order(gen_hh, test_hh, test_hh["WGTP_eff"].to_numpy(), V.HH_VARS, orders=(1, 2))
res["5_income"] = V.income_metrics(gen_hh, test_hh, test_hh["WGTP_eff"].to_numpy())
res["6_couple_age_gap"] = {"gen": V.couple_age_gap(gen_pp, "hh_id"),
                           "test": V.couple_age_gap(test_pp, "SERIALNO")}
res["7_spatial_hh"] = V.per_puma_srmse(gen_hh, test_hh, "WGTP_eff", V.HH_VARS, "hh")
res["8_structural_zeros"] = count_structural_zeros(gen_pp, hh=gen_hh)
# HONEST DISCLOSURE (TRB MJ-4): the post-patch count above is 0 BY CONSTRUCTION
# (apply_constraints overwrites illegal combos, then this checks them) -- a
# tautological check. The informative number is the PRE-patch illegal-combo rate,
# i.e. how many age-impossible combinations the decoder actually produced before
# the deterministic patch. generate.py stashes it on gen_pp.attrs.
res["8b_prepatch_illegal_combos"] = {
    **gen_pp.attrs.get("prepatch_structural_zeros", {}),
    "note": "PRE-patch decoder output; apply_constraints then overwrites these so 8_structural_zeros==0 "
            "(that post-patch check is tautological). This pre-patch rate is the honest measure.",
}
res["9_sampling_zeros"] = V.sampling_zeros(gen_pp, train_pp, test_pp)
res["10_memorization"] = V.memorization(gen_pp, train_pp)
res["11_coherence"] = V.coherence(gen_hh, gen_pp)

# 12 identifiability floors: marginal SRMSE between two halves of TEST
rng = np.random.default_rng(0)
te = test_hh.sample(frac=1.0, random_state=0); half = len(te) // 2
floor = {}
for name, n, base in V.HH_VARS:
    a, b = te.iloc[:half], te.iloc[half:]
    pa = V._dist(a[name], a["WGTP_eff"].to_numpy(), n, base)
    pb = V._dist(b[name], b["WGTP_eff"].to_numpy(), n, base)
    floor[name] = V.srmse(pa, pb)
res["12_identifiability_floor_hh"] = floor

(OUT / "results.json").write_text(json.dumps(res, indent=2, default=float))

# ── summary figure ───────────────────────────────────────────────────────
plt.rcParams.update({"figure.dpi": 110, "font.size": 8})
fig, ax = plt.subplots(2, 2, figsize=(15, 9))
mh = res["2_marginals_hh"]; mp = res["2_marginals_pp"]
names = list(mh) + list(mp); tvs = [mh[k]["tv"] for k in mh] + [mp[k]["tv"] for k in mp]
ax[0, 0].bar(range(len(names)), tvs, color="#4C72B0")
ax[0, 0].set_xticks(range(len(names))); ax[0, 0].set_xticklabels(names, rotation=90, fontsize=6)
ax[0, 0].axhline(0.03, color="red", ls="--", label="0.03 ref"); ax[0, 0].legend()
ax[0, 0].set_title("F1 marginal TV (held-out)", fontweight="bold")
orders = ["1way_mean_srmse", "2way_mean_srmse", "3way_mean_srmse"]
ax[0, 1].bar(["1-way", "2-way", "3-way"], [res["3_joints_pp"][o] for o in orders], color="#55A868")
ax[0, 1].set_title("F8 person joint SRMSE by order", fontweight="bold")
inc = res["5_income"]
labels = ["P50", "P95", "P99"]; bias = [inc[f"P{q}_bias_pct"] for q in (50, 95, 99)]
ax[1, 0].bar(labels, bias, color="#C44E52"); ax[1, 0].axhline(0, color="k", lw=0.5)
ax[1, 0].set_title("F5 income quantile bias % (gen vs test)", fontweight="bold")
sh = [inc["share_gt_300k_ref"], inc["share_gt_300k_gen"], inc["share_gt_1m_ref"]*10, inc["share_gt_1m_gen"]*10]
ax[1, 1].bar(["ref>300k", "gen>300k", "ref>1M×10", "gen>1M×10"], sh, color="#8172B3")
ax[1, 1].set_title("F5 income tail shares (%)", fontweight="bold")
sz = res["8_structural_zeros"]["total"]; cg = res["6_couple_age_gap"]
fig.suptitle(f"Validation vs held-out 2016 TEST — structural zeros={sz} | "
             f"couple gap gen {cg['gen']:.1f}y vs test {cg['test']:.1f}y | "
             f"Σincome exact {res['11_coherence']['sigma_income_exact_pct']:.0f}%",
             fontsize=12, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.96]); fig.savefig(OUT / "summary.png"); plt.close(fig)

# ── print pass/fail ──────────────────────────────────────────────────────
print("\n================ VALIDATION SUMMARY (held-out 2016 test) ================")
worst_tv = max(max(v["tv"] for v in mh.values()), max(v["tv"] for v in mp.values()))
print(f"F1 worst marginal TV: {worst_tv:.4f}  (ref ~0.03)")
print(f"F8 joint SRMSE: 1-way {res['3_joints_pp']['1way_mean_srmse']:.3f} | "
      f"2-way {res['3_joints_pp']['2way_mean_srmse']:.3f} | 3-way {res['3_joints_pp']['3way_mean_srmse']:.3f}")
print(f"F5 income: P95 bias {inc['P95_bias_pct']:+.1f}% | P99 bias {inc['P99_bias_pct']:+.1f}% | "
      f">300k gen {inc['share_gt_300k_gen']:.2f}% vs ref {inc['share_gt_300k_ref']:.2f}% | "
      f">1M gen {inc['share_gt_1m_gen']:.3f}% vs ref {inc['share_gt_1m_ref']:.3f}% | max gen ${inc['max_gen']:,.0f}")
print(f"S6 couple age gap: gen {cg['gen']:.2f}y vs test {cg['test']:.2f}y")
pre = res["8b_prepatch_illegal_combos"]
print(f"STRUCTURAL ZEROS (post-patch, TAUTOLOGICAL): {sz}  {'PASS' if sz==0 else 'FAIL'}")
print(f"  PRE-patch illegal combos (the honest number): total {pre.get('total','?')} "
      f"= {pre.get('rate_pct',float('nan')):.3f}% of persons "
      f"[employed<16 {pre.get('employed_under16','?')}, retiree<62 {pre.get('retiree_under62','?')}, "
      f"license<16 {pre.get('license_under16','?')}, spouse<16 {pre.get('spouse_under16','?')}, "
      f"toddler>5 {pre.get('toddler_over5','?')}, nontoddler<6 {pre.get('nontoddler_under6','?')}, "
      f"age_outside_bin {pre.get('age_outside_bin','?')}]")
szz = res["9_sampling_zeros"]
print(f"Sampling zeros: test-only cells {szz['test_only_cells']}, recovered {szz['test_only_recovered_by_gen']} "
      f"({szz['recovery_rate']*100:.0f}%); novel-not-in-test {szz['novel_not_in_test']}")
print(f"Memorization: {res['10_memorization']['frac_gen_types_in_train']*100:.1f}% gen person-types seen in train")
print(f"Coherence: Σincome exact {res['11_coherence']['sigma_income_exact_pct']:.1f}% | "
      f"one householder {res['11_coherence']['one_householder_pct']:.1f}%")
print(f"saved → {OUT}")
