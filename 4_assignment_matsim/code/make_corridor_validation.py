#!/usr/bin/env python3
"""Corridor-level validation for the I-695 pricing study: the tolled ring + every diversion-
relevant corridor. One TRB-style figure per corridor + outlier diagnosis (which stations are
far off and the mechanical reason: one-direction matching, tier mismatch, ramp contamination,
through-traffic scope, or genuine model error).

Usage: python3 make_corridor_validation.py <linkstats.txt.gz> <out_dir>
"""
import sys, os, re, gzip
import numpy as np, pandas as pd
import xml.etree.ElementTree as ET
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
LS, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
import os
AADT = os.environ.get("AADT_FILE", f"{ROOT}/network_validation_2023/transitfix/aadt/aadt_validation_2023_qa.csv")
NET  = f"{ROOT}/network_validation_2023/network_audit/bmr_network_pt_speedcal_capfix_v13.xml.gz"
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix", "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 7.5,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.8})
def save(fig, name):
    fig.savefig(f"{OUT}/{name}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{OUT}/{name}.pdf", bbox_inches="tight")
    plt.close(fig); print(f"  saved {name}")

# corridors relevant to I-695 pricing: the ring itself + radial freeways + parallel arterials
CORRIDORS = [
    ("I-695 Baltimore Beltway (tolled)", "IS", 695), ("I-95", "IS", 95),
    ("I-895 Harbor Tunnel", "IS", 895), ("I-83", "IS", 83), ("I-70", "IS", 70),
    ("I-97", "IS", 97), ("I-795", "IS", 795), ("MD-295 Balt-Wash Pkwy", "MD", 295),
    ("US-40 (I-70/I-695 parallel)", "US", 40), ("US-1 (I-95 parallel)", "US", 1),
    ("MD-2 Ritchie Hwy", "MD", 2), ("MD-140 Reisterstown Rd", "MD", 140),
]

ls = pd.read_csv(LS, sep="\t", low_memory=False, dtype={"LINK":str})
ls["vol24"] = pd.to_numeric(ls["HRS0-24avg"], errors="coerce") * 10.0
vol = dict(zip(ls.LINK, ls.vol24))
df = pd.read_csv(AADT)
df = df[df.link_ids.notna() & (df.n_links > 0) & (df.obs_AADT > 0)].copy()
df["m"] = df.link_ids.apply(lambda s: sum(vol.get(l.strip(), 0.0) for l in str(s).split(";") if l.strip()))
df["rd"] = (df.m - df.obs_AADT) / df.obs_AADT

# link attributes for outlier diagnosis
need = set()
for _, r in df.iterrows():
    for l in str(r.link_ids).split(";"):
        if l.strip(): need.add(l.strip())
LA = {}
for _, el in ET.iterparse(gzip.open(NET, "rb"), events=("end",)):
    if el.tag != "link": continue
    i = el.get("id")
    if i in need:
        hw = None
        for a in el.findall("attributes/attribute"):
            if a.get("name") == "osm:way:highway": hw = a.text; break
        LA[i] = (hw or "?", float(el.get("permlanes", 1)), float(el.get("capacity", 0)))
    el.clear()

summary, outliers = [], []
for label, pref, rte in CORRIDORS:
    s = df[(df.ID_PREFIX == pref) & (df.ID_RTE_NO == rte)].copy()
    # keep the corridor's mainline tier only (drop cross-street stations that share the route no.)
    main_fac = s.groupby("facility").obs_AADT.sum().idxmax() if len(s) else None
    s = s[s.facility == main_fac].sort_values("obs_AADT", ascending=False).reset_index(drop=True)
    if len(s) < 3:
        print(f"  [skip {label}: n={len(s)}]"); continue
    ratio = s.m.sum() / s.obs_AADT.sum()
    summary.append(dict(corridor=label, n=len(s), facility=main_fac, obs=int(s.obs_AADT.sum()),
                        model=int(s.m.sum()), vol_ratio=round(ratio, 3),
                        median_rd=round(float(np.median(s.rd)), 3),
                        within50=round(100*float((s.rd.abs() <= 0.5).mean()), 1)))
    # figure: obs vs sim bars, stations sorted by observed volume
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:28]
    fig, ax = plt.subplots(figsize=(max(3.6, 0.16*len(s)+1.6), 3.1))
    x = np.arange(len(s)); w = 0.42
    ax.bar(x-w/2, s.obs_AADT/1e3, w, color="0.72", label="Observed AADT 2023")
    ax.bar(x+w/2, s.m/1e3, w, color="#0072B2", label="Simulated (×10)")
    for xi, rd in zip(x, s.rd):
        if abs(rd) > 0.5:
            ax.plot(xi+w/2, s.m.iloc[xi]/1e3, marker="v" if rd < 0 else "^",
                    color="#D55E00", ms=4, lw=0)
    ax.set_xticks(x[::max(1, len(s)//14)])
    ax.set_xticklabels(s.LOCATION_ID[::max(1, len(s)//14)], rotation=60, fontsize=5.5)
    ax.set_ylabel("Daily volume (thousands)")
    ax.set_title(f"{label} — n={len(s)}, $\\Sigma$sim/$\\Sigma$obs = {ratio:.2f}, median rel. diff. {100*np.median(s.rd):+.0f}%")
    from matplotlib.lines import Line2D
    h, l = ax.get_legend_handles_labels()
    h += [Line2D([0], [0], marker="^", color="none", markerfacecolor="#D55E00", ms=5,
                 label="station outlier: sim > obs by 50%+"),
          Line2D([0], [0], marker="v", color="none", markerfacecolor="#D55E00", ms=5,
                 label="station outlier: sim < obs by 50%+")]
    ax.legend(handles=h, frameon=False, fontsize=7)
    fig.tight_layout(); save(fig, f"corridor_{slug}")
    # outlier diagnosis: |rd| > 50%
    for _, r in s[s.rd.abs() > 0.5].iterrows():
        lids = [l.strip() for l in str(r.link_ids).split(";") if l.strip()]
        tiers = [LA.get(l, ("?", 0, 0))[0] for l in lids]
        mainline_tiers = {"motorway", "trunk", "primary", "secondary", "tertiary"}
        n_ramp = sum(t.endswith("_link") for t in tiers)
        expected = {"Interstate/Freeway": {"motorway", "trunk"},
                    "Principal Arterial": {"trunk", "primary"},
                    "Minor Arterial": {"primary", "secondary"},
                    "Collector/Local": {"secondary", "tertiary", "residential", "unclassified"}}
        n_wrong = sum(t not in expected.get(r.facility, mainline_tiers) and not t.endswith("_link") for t in tiers)
        if r.facility == "Interstate/Freeway" and len(lids) == 1:
            why = "ONE-DIRECTION match (bidirectional count vs single link) -> reads ~0.5x"
        elif n_ramp == len(lids):
            why = "matched ONLY to ramp links -> not mainline volume"
        elif n_wrong > 0:
            why = f"tier mismatch: {n_wrong}/{len(lids)} links are {sorted(set(tiers))}"
        elif r.rd < 0 and pref == "IS":
            why = "under: consistent w/ resident-only scope (through+truck) and/or residual congestion"
        elif r.rd > 0:
            why = "over: model routes excess onto this segment (check parallel capacity)"
        else:
            why = "under: unexplained -> candidate for link-level review"
        outliers.append(dict(corridor=label, station=r.LOCATION_ID, obs=int(r.obs_AADT),
                             model=int(r.m), rel_diff=round(float(r.rd), 2),
                             n_links=len(lids), tiers=";".join(sorted(set(tiers))), diagnosis=why))

sm = pd.DataFrame(summary); sm.to_csv(f"{OUT}/corridor_summary.csv", index=False)
ol = pd.DataFrame(outliers); ol.to_csv(f"{OUT}/corridor_outliers.csv", index=False)
print("\n=== CORRIDOR SUMMARY ===")
print(sm.to_string(index=False))
print(f"\n=== OUTLIERS (|rel diff| > 50%): {len(ol)} stations ===")
if len(ol): print(ol.groupby("diagnosis").size().to_string())
