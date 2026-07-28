#!/usr/bin/env python3
"""Station-matching QA filter for AADT validation.

Drops stations whose station->link matching is MECHANICALLY unreliable, using criteria that are
independent of model performance (no cherry-picking):
  D1 one-direction match on a major two-way facility: facility in {Interstate/Freeway, Principal
     Arterial} with obs_AADT > 10k but matched links all pointing one way -> the bidirectional
     count is compared against half the road; reads ~0.5x regardless of model quality.
  D2 ramp-only match: a mainline station whose matched links are all *_link ramps.
  D3 tier-incompatible match: no matched link belongs to the facility's compatible OSM tier set
     (e.g. a freeway station matched only to secondary/residential links).
Already excluded upstream: stations with no matched links at all.

Writes: aadt_validation_2023_qa.csv (kept rows, same schema) + aadt_station_qa_log.csv (all rows
with keep/drop + reason). Prints the before/after per-tier effect.
"""
import gzip, xml.etree.ElementTree as ET
import numpy as np, pandas as pd

ROOT = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
AADT = f"{ROOT}/network_validation_2023/transitfix/aadt/aadt_validation_2023_cleaned.csv"
NET  = f"{ROOT}/network_validation_2023/network_audit/bmr_network_pt_speedcal_capfix_v13.xml.gz"
OUTK = f"{ROOT}/network_validation_2023/transitfix/aadt/aadt_validation_2023_qa.csv"
OUTL = f"{ROOT}/network_validation_2023/transitfix/aadt/aadt_station_qa_log.csv"

COMPAT = {"Interstate/Freeway": {"motorway", "motorway_link", "trunk", "trunk_link"},
          "Principal Arterial": {"trunk", "trunk_link", "primary", "primary_link", "motorway"},
          "Minor Arterial": {"primary", "secondary", "tertiary"},
          "Collector/Local": {"secondary", "tertiary", "residential", "unclassified", "living_street"},
          "Ramp": {"motorway_link", "trunk_link", "primary_link"}}

df = pd.read_csv(AADT)
need = set()
for s in df.link_ids.dropna():
    for l in str(s).split(";"):
        if l.strip(): need.add(l.strip())

nodes, links = {}, {}
for _, el in ET.iterparse(gzip.open(NET, "rb"), events=("end",)):
    if el.tag == "node":
        nodes[el.get("id")] = (float(el.get("x")), float(el.get("y"))); el.clear()
    elif el.tag == "link":
        i = el.get("id")
        if i in need:
            hw = None
            for a in el.findall("attributes/attribute"):
                if a.get("name") == "osm:way:highway": hw = a.text; break
            links[i] = (el.get("from"), el.get("to"), hw or "?")
        el.clear()

rows = []
for _, r in df.iterrows():
    if pd.isna(r.link_ids) or r.n_links == 0 or r.obs_AADT <= 0:
        rows.append("unmatched_upstream"); continue
    lids = [l.strip() for l in str(r.link_ids).split(";") if l.strip()]
    tiers = [links[l][2] for l in lids if l in links]
    # D3 tier compatibility
    ok_tier = any(t in COMPAT.get(r.facility, set()) for t in tiers)
    # D2 ramp-only (for mainline facilities)
    ramp_only = r.facility != "Ramp" and len(tiers) > 0 and all(t.endswith("_link") for t in tiers)
    # D1 direction coverage via link bearings
    vec = []
    for l in lids:
        if l not in links: continue
        f, t, _ = links[l]
        if f in nodes and t in nodes:
            dx, dy = nodes[t][0]-nodes[f][0], nodes[t][1]-nodes[f][1]
            n = np.hypot(dx, dy)
            if n > 0: vec.append((dx/n, dy/n))
    both_dir = False
    for i in range(len(vec)):
        for j in range(i+1, len(vec)):
            if vec[i][0]*vec[j][0] + vec[i][1]*vec[j][1] < -0.3:   # >~107 deg apart
                both_dir = True; break
        if both_dir: break
    one_dir_major = (r.facility in ("Interstate/Freeway", "Principal Arterial")
                     and r.obs_AADT > 10000 and len(vec) >= 1 and not both_dir)
    if ramp_only: rows.append("D2_ramp_only")
    elif not ok_tier: rows.append("D3_tier_incompatible")
    elif one_dir_major: rows.append("D1_one_direction_major")
    else: rows.append("keep")

df["qa"] = rows
log = df[["LOCATION_ID", "facility", "obs_AADT", "n_links", "qa"]]
log.to_csv(OUTL, index=False)
kept = df[df.qa == "keep"].drop(columns="qa")
kept.to_csv(OUTK, index=False)

print("=== QA verdicts ===")
print(df.qa.value_counts().to_string())
print("\n=== drops by facility (excl. upstream-unmatched) ===")
d = df[~df.qa.isin(["keep", "unmatched_upstream"])]
print(d.groupby(["facility", "qa"]).size().to_string())
print(f"\nkept {len(kept)} stations ({100*len(kept)/len(df):.0f}%); "
      f"dropped obs share: {100*d.obs_AADT.sum()/df.obs_AADT.sum():.1f}% of total observed volume")
