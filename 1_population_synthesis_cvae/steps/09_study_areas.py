#!/usr/bin/env python3
"""STEP 09 — county-wise validation for the Baltimore and NoVA study areas.

Compares the generated population (step 04) to the PUMS reference, restricted to each study
area and each county (county = its set of PUMAs, majority-assigned from the zone system).
Outputs → outputs/09_study_areas/{study_area_summary.csv, <area>_*.png}

Note: the zone system merges VA independent cities into parents — 51942 = Prince William +
Manassas + Manassas Park; 51919 = Fairfax + Fairfax City + Falls Church.
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from vaelib import config, crosswalks, validate as V

ap = argparse.ArgumentParser()
ap.add_argument("--ref", default="full", choices=["full", "test"],
                help="reference: full PUMS (regional coverage) or held-out test split")
args = ap.parse_args()

GEN = config.OUTPUTS_DIR / "04_generated"; PRE = config.OUTPUTS_DIR / "01_preprocessed"
OUT = config.OUTPUTS_DIR / "09_study_areas"; OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"figure.dpi": 150, "font.size": 10, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.spines.top": False, "axes.spines.right": False, "savefig.bbox": "tight"})

BALT = {24003: "Anne Arundel", 24510: "Baltimore City", 24005: "Baltimore County",
        24027: "Howard", 24025: "Harford", 24013: "Carroll"}
NOVA = {51510: "Alexandria", 51013: "Arlington", 51107: "Loudoun",
        51942: "Prince William (+Manassas, Manassas Park)", 51919: "Fairfax (+Fairfax City, Falls Church)"}
AREAS = {"baltimore": BALT, "nova": NOVA}

# PUMA -> majority county (by HH-weight), then county -> PUMA set
zt = crosswalks.build_zone_table()
maj = (zt.groupby(["puma_key", "county_fips"])["zone_weight_hh"].sum().reset_index()
       .sort_values("zone_weight_hh").drop_duplicates("puma_key", keep="last"))
puma_county = dict(zip(maj["puma_key"], maj["county_fips"]))
county_pumas = {}
for pk, c in puma_county.items():
    county_pumas.setdefault(int(c), []).append(pk)

gen_hh = pd.read_parquet(GEN / "hh.parquet"); gen_pp = pd.read_parquet(GEN / "pp.parquet")
hh = pd.read_parquet(PRE / "hh.parquet"); pp = pd.read_parquet(PRE / "pp.parquet")
if args.ref == "test":
    import json
    sp = np.load(config.OUTPUTS_DIR / "03_training" / "full" / "split_idx.npz")
    keep = set(hh.reset_index(drop=True).loc[sp["test"], "SERIALNO"])
    hh = hh[hh.SERIALNO.isin(keep)]; pp = pp[pp.SERIALNO.isin(keep)]
print(f"reference = {args.ref} PUMS", flush=True)

HHV = [("dwellingType", 5, 1), ("tenure", 2, 1), ("autos", 5, 0), ("income_bin", config.n_hh_income_bins(), 0)]
PPV = [("age_bin", 18, 0), ("gender", 2, 1), ("race", 5, 1), ("occupation", 6, 1),
       ("driversLicense", 2, 0), ("relationship", 8, 0), ("income_bin", config.n_pp_income_bins(), 0)]


def tvs(gsub_hh, gsub_pp, rsub_hh, rsub_pp):
    out = {}
    for nm, n, b in HHV:
        out["hh:" + nm] = V.tv(V._dist(rsub_hh[nm], rsub_hh["WGTP_eff"].to_numpy(), n, b),
                               V._dist(gsub_hh[nm], np.ones(len(gsub_hh)), n, b))
    for nm, n, b in PPV:
        out["pp:" + nm] = V.tv(V._dist(rsub_pp[nm], rsub_pp["PWGTP_eff"].to_numpy(), n, b),
                               V._dist(gsub_pp[nm], np.ones(len(gsub_pp)), n, b))
    return out


rows = []
for area, counties in AREAS.items():
    units = [("ALL " + area, list(counties))] + [(nm, [c]) for c, nm in counties.items()]
    tv_matrix = {}
    for label, clist in units:
        pumas = set(pk for c in clist for pk in county_pumas.get(int(c), []))
        gh = gen_hh[gen_hh.puma_key.isin(pumas)]; gp = gen_pp[gen_pp.puma_key.isin(pumas)]
        rh = hh[hh.puma_key.isin(pumas)]; rp = pp[pp.puma_key.isin(pumas)]
        if len(gh) == 0 or len(rh) == 0:
            continue
        t = tvs(gh, gp, rh, rp)
        gmed = np.median(gh["income_hh"]); rmed = V._wq(rh["income_hh"].to_numpy(), rh["WGTP_eff"].to_numpy(), .5)
        rows.append({"area": area, "unit": label, "n_pumas": len(pumas),
                     "gen_hh": len(gh), "ref_hh_wt": int(rh["WGTP_eff"].sum()),
                     "gen_persons_per_hh": len(gp) / len(gh),
                     "income_median_gen": int(gmed), "income_median_ref": int(rmed),
                     "income_median_err_pct": (gmed - rmed) / max(rmed, 1) * 100,
                     "mean_marginal_TV": np.mean(list(t.values())), **t})
        tv_matrix[label] = t

    # figure: county × variable TV heatmap
    labels = list(tv_matrix); variables = list(next(iter(tv_matrix.values())))
    M = np.array([[tv_matrix[l][v] for v in variables] for l in labels])
    fig, ax = plt.subplots(figsize=(max(8, len(variables) * 0.8), 1 + 0.5 * len(labels)))
    im = ax.imshow(M, cmap="YlOrRd", vmin=0, vmax=max(0.06, M.max()), aspect="auto")
    ax.set_xticks(range(len(variables))); ax.set_xticklabels(variables, rotation=90)
    ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels)
    for i in range(len(labels)):
        for j in range(len(variables)):
            ax.text(j, i, f"{M[i,j]:.02f}", ha="center", va="center", fontsize=7,
                    color="white" if M[i, j] > 0.04 else "black")
    ax.set_title(f"{area.upper()} study area — marginal TV by county (ref={args.ref})", fontweight="bold")
    fig.colorbar(im, fraction=0.025)
    fig.savefig(OUT / f"{area}_county_TV_heatmap.png", dpi=300); fig.savefig(OUT / f"{area}_county_TV_heatmap.pdf")
    plt.close(fig)

    # figure: age_bin overlay for the whole study area
    pumas = set(pk for c in counties for pk in county_pumas.get(int(c), []))
    gp = gen_pp[gen_pp.puma_key.isin(pumas)]; rp = pp[pp.puma_key.isin(pumas)]
    pr = V._dist(rp["age_bin"], rp["PWGTP_eff"].to_numpy(), 18, 0); pg = V._dist(gp["age_bin"], np.ones(len(gp)), 18, 0)
    fig, ax = plt.subplots(figsize=(9, 5)); x = np.arange(18)
    ax.bar(x - 0.2, pr * 100, 0.4, color="#2c6fbb", label="PUMS")
    ax.bar(x + 0.2, pg * 100, 0.4, color="#c4423a", label="VAE")
    ax.set_xlabel("age bin (5-yr)"); ax.set_ylabel("% of persons")
    ax.set_title(f"{area.upper()} — age distribution (TV={V.tv(pr,pg):.3f})"); ax.legend(frameon=False)
    fig.savefig(OUT / f"{area}_age.png", dpi=300); fig.savefig(OUT / f"{area}_age.pdf"); plt.close(fig)

df = pd.DataFrame(rows)
df.to_csv(OUT / "study_area_summary.csv", index=False)
print("\n=== STUDY-AREA SUMMARY ===")
print(df[["area", "unit", "gen_hh", "gen_persons_per_hh", "income_median_gen",
          "income_median_ref", "income_median_err_pct", "mean_marginal_TV"]].to_string(index=False))
print(f"\nsaved → {OUT}")
