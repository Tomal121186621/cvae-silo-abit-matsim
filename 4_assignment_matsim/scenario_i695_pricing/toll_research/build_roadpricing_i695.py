#!/usr/bin/env python3
"""
Build a MATSim RoadPricing file for the I-695 (Baltimore Beltway) time-of-day toll.

Design (see scenarios/02_i695_congestion_pricing/toll/i695_toll_schema.md):
  * type="link" : each tolled I-695 link is charged when a car enters it.
  * The per-link <cost amount> is made DISTANCE-PROPORTIONAL by setting
        amount = perMileRate(window) * link_length_miles
    so summing over a trip's I-695 links reproduces a per-mile toll grounded in
    the MD I-95 ETL / ICC (MD-200) per-mile precedents. A whole-facility per-mile
    charge is exactly what "distance" type does; we emit it as per-link amounts so
    the file is valid as type="link" (each link tolled once per traversal).
  * Time-of-day windows follow the MDTA ETL/ICC peak / off-peak / overnight split.

Usage:
  python build_roadpricing_i695.py <schema: A|B> <out.xml>
Defaults: schema A -> ../02_i695_congestion_pricing/toll/roadpricing_i695.xml
"""
import gzip, sys, os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
NET  = os.path.join(HERE, "..", "01_base_no_pricing", "input", "network", "bmr_network_pt.xml.gz")
if not os.path.exists(NET):
    NET = os.path.join(HERE, "..", "..", "input", "network", "bmr_network_pt.xml.gz")
LINKS_FILE = os.path.join(HERE, "i695_link_ids.txt")
MI_PER_M = 1.0 / 1609.344

# per-mile rates ($/mi) by schema and window  (see toll schema doc for grounding)
SCHEMAS = {
    "A": {"name": "i695-tod-moderate", "peak": 0.25, "offpeak": 0.18, "night": 0.10},
    "B": {"name": "i695-tod-high",     "peak": 0.40, "offpeak": 0.30, "night": 0.15},
}

# (start, end, window-key) in HH:MM:SS.  Night wraps midnight; sim runs 0-36h so the
# late-night block extends to 30:00:00 to cover post-midnight legs of the modeled day.
WINDOWS = [
    ("00:00:00", "05:00:00", "night"),
    ("05:00:00", "06:00:00", "offpeak"),
    ("06:00:00", "09:00:00", "peak"),
    ("09:00:00", "15:00:00", "offpeak"),
    ("15:00:00", "19:00:00", "peak"),
    ("19:00:00", "23:00:00", "offpeak"),
    ("23:00:00", "30:00:00", "night"),
]

def load_link_ids():
    ids = []
    with open(LINKS_FILE) as f:
        for ln in f:
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                ids.append(ln)
    return set(ids), ids  # set for lookup, list to preserve order

def load_lengths(id_set):
    lengths = {}
    op = gzip.open if NET.endswith(".gz") else open
    with op(NET, "rb") as fh:
        for ev, el in ET.iterparse(fh, events=("end",)):
            if el.tag == "link":
                lid = el.get("id")
                if lid in id_set:
                    lengths[lid] = float(el.get("length"))
                el.clear()
    return lengths

def main():
    schema_key = (sys.argv[1] if len(sys.argv) > 1 else "A").upper()
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        HERE, "..", "02_i695_congestion_pricing", "toll", "roadpricing_i695.xml")
    sc = SCHEMAS[schema_key]

    id_set, id_order = load_link_ids()
    lengths = load_lengths(id_set)
    missing = id_set - set(lengths)
    tot_mi = sum(lengths.values()) * MI_PER_M

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!DOCTYPE roadpricing SYSTEM "http://www.matsim.org/files/dtd/roadpricing_v1.dtd">')
    lines.append(f'<roadpricing type="link" name="{sc["name"]}">')
    lines.append(f'  <description>I-695 Baltimore Beltway time-of-day toll (Schema {schema_key}). '
                 f'Per-link amount = perMileRate x link_length_miles so the facility toll is '
                 f'distance-proportional. Peak={sc["peak"]} Off-peak={sc["offpeak"]} '
                 f'Night={sc["night"]} $/mi. {len(lengths)} tolled links, {tot_mi:.1f} directional miles.</description>')
    lines.append('  <links>')
    for lid in id_order:
        if lid not in lengths:
            continue
        mi = lengths[lid] * MI_PER_M
        lines.append(f'    <link id="{lid}">')
        for st, et, wk in WINDOWS:
            amt = round(sc[wk] * mi, 5)
            lines.append(f'      <cost start_time="{st}" end_time="{et}" amount="{amt}" />')
        lines.append('    </link>')
    lines.append('  </links>')
    lines.append('</roadpricing>')

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Schema {schema_key} ({sc['name']})")
    print(f"  tolled links written : {len(lengths)}")
    print(f"  total directional mi : {tot_mi:.2f}")
    print(f"  missing lengths      : {len(missing)}")
    print(f"  full-loop toll (peak): ${sc['peak']*tot_mi/2:.2f} one-way")
    print(f"  10-mi trip (peak/off/night): "
          f"${sc['peak']*10:.2f} / ${sc['offpeak']*10:.2f} / ${sc['night']*10:.2f}")
    print(f"  written -> {os.path.abspath(out)}")

if __name__ == "__main__":
    main()
