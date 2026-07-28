#!/usr/bin/env python3
"""
Identify the MATSim network links that comprise I-695 (the Baltimore Beltway)
for a congestion-pricing / road-pricing scenario.

Strategy (attribute-based, PREFERRED):
    The network links carry OSM metadata as child <attributes> blocks.
    There is NO `osm:way:ref` field, but there IS an `osm:way:name` field.
    In OSM, I-695 mainline is consistently named "Baltimore Beltway"
    (I-495 around Washington DC is "Capital Beltway" and is EXCLUDED).
    We therefore match links whose osm:way:name == "Baltimore Beltway"
    (case-insensitive) and record their highway class for reporting.

Reads gzipped MATSim network XML with iterparse for memory safety.
Does NOT modify the network file.
"""
import gzip
import xml.etree.ElementTree as ET
from collections import Counter

NETWORK = ("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/"
           "Updated MATSim/input/network/bmr_network_pt.xml.gz")
OUT_IDS = ("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/"
           "Updated MATSim/scenarios/toll_research/i695_link_ids.txt")

TARGET_NAME = "baltimore beltway"   # I-695; matched case-insensitively

matched = []          # list of (link_id, length, freespeed, highway)
hw_counter = Counter()
fs_counter = Counter()

context = ET.iterparse(gzip.open(NETWORK, "rb"), events=("start", "end"))
cur = None  # attributes of the link currently being parsed

for event, elem in context:
    tag = elem.tag
    if event == "start" and tag == "link":
        cur = {
            "id": elem.get("id"),
            "length": float(elem.get("length", "0")),
            "freespeed": float(elem.get("freespeed", "0")),
            "name": None,
            "highway": None,
        }
    elif event == "end":
        if tag == "attribute" and cur is not None:
            name = elem.get("name")
            if name == "osm:way:name":
                cur["name"] = (elem.text or "").strip()
            elif name == "osm:way:highway":
                cur["highway"] = (elem.text or "").strip()
        elif tag == "link" and cur is not None:
            nm = (cur["name"] or "").lower()
            if nm == TARGET_NAME:
                matched.append((cur["id"], cur["length"],
                                cur["freespeed"], cur["highway"]))
                hw_counter[cur["highway"]] += 1
                # freespeed bucket in mph (m/s -> mph)
                mph = cur["freespeed"] * 2.23694
                bucket = f"{int(mph // 5) * 5}-{int(mph // 5) * 5 + 5} mph"
                fs_counter[bucket] += 1
            cur = None
            elem.clear()

total_m = sum(m[1] for m in matched)
total_mi = total_m / 1609.344

print(f"Matched I-695 (Baltimore Beltway) links: {len(matched)}")
print(f"Total length: {total_m:,.1f} m = {total_mi:,.2f} miles")
print(f"Highway class breakdown: {dict(hw_counter)}")
print(f"Freespeed buckets: {dict(fs_counter)}")

with open(OUT_IDS, "w") as f:
    f.write(f"# I-695 Baltimore Beltway link IDs -- MATSim network bmr_network_pt.xml.gz\n")
    f.write(f"# Strategy: osm:way:name == 'Baltimore Beltway' (case-insensitive)\n")
    f.write(f"# Count: {len(matched)} links | Total length: {total_m:.1f} m = {total_mi:.2f} miles\n")
    f.write(f"# Highway classes: {dict(hw_counter)}\n")
    for link_id, *_ in sorted(matched, key=lambda r: int(r[0]) if r[0].isdigit() else r[0]):
        f.write(f"{link_id}\n")

print(f"Wrote {len(matched)} link IDs to {OUT_IDS}")
