#!/usr/bin/env python3
"""Shared definitions for the 2023 NPMRDS speed calibration + validation.

Implements the link-type / sub-category scheme and the 6 time periods of
He, Chow, Ozbay et al. (Transport Policy) Section 4.2.2, Eqs (9)-(10), Table 3.

  Link type  L=1 Freeway  : OSM {motorway, motorway_link, trunk, trunk_link}
             L=2 Arterial : OSM {primary/secondary/tertiary (+ _link)} split into
                            3 sub-categories j=1,2,3 (their 22.2 / 15.0 / 8.3 m/s).
  Periods    6-9AM, 9AM-12PM, 12-3PM, 3-6PM, 6-9PM, 9PM-6AM.

NPMRDS = FHWA National Performance Management Research Data Set (INRIX/HERE probe
speeds), pulled from the RITIS Massive Data Downloader (see data/npmrds_2023/README_ACCESS.md).
It is the free public-sector substitute for the paper's commercial INRIX feed.
"""
import gzip, re
from pathlib import Path
import numpy as np

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
NPMRDS_DIR = ROOT/"data/npmrds_2023"
SPEED_OUT  = ROOT/"network_validation_2023/speed"
MS_TO_MPH  = 2.2369362920544

# ---- 6 time periods (paper Sec 4.2.2). key -> (label, set-of-hours) ------------
PERIODS = [
    ("6-9AM",   [6, 7, 8]),
    ("9AM-12PM",[9, 10, 11]),
    ("12-3PM",  [12, 13, 14]),
    ("3-6PM",   [15, 16, 17]),
    ("6-9PM",   [18, 19, 20]),
    ("9PM-6AM", [21, 22, 23, 0, 1, 2, 3, 4, 5]),
]
PERIOD_ORDER = [p[0] for p in PERIODS]
HOUR2PERIOD  = {h: k for k, hrs in PERIODS for h in hrs}
# absolute start-seconds used when writing time-variant NetworkChangeEvents
PERIOD_START_S = {"6-9AM":6*3600, "9AM-12PM":9*3600, "12-3PM":12*3600,
                  "3-6PM":15*3600, "6-9PM":18*3600, "9PM-6AM":21*3600}

# ---- link-type classification from OSM highway tag -----------------------------
FREEWAY_HWY  = {"motorway", "motorway_link", "trunk", "trunk_link"}
ARTERIAL_SUB = {                       # OSM class -> arterial sub-category j (1..3)
    "primary": 1, "primary_link": 1,   # paper base v0 ~ 22.2 m/s
    "secondary": 2, "secondary_link": 2,  # ~ 15.0 m/s
    "tertiary": 3, "tertiary_link": 3,    # ~ 8.3 m/s
}

def classify(hwy):
    """Return (type, subcat) where type in {'freeway','arterial',None}.

    None => local/collector (residential/unclassified/service/...) — not covered by
    NPMRDS nor calibrated by the paper; such links keep their base free speed.
    """
    if hwy in FREEWAY_HWY:
        return ("freeway", 0)
    if hwy in ARTERIAL_SUB:
        return ("arterial", ARTERIAL_SUB[hwy])
    return (None, 0)

# key used in the factor table for a (type, subcat) group
def group_key(typ, sub):
    return "freeway" if typ == "freeway" else f"arterial_j{sub}"

# ---- MATSim network parser (car links, with length + OSM class) ----------------
_LSTART = re.compile(
    r'<link id="([^"]+)" from="([^"]+)" to="([^"]+)" length="([^"]+)" '
    r'freespeed="([^"]+)" capacity="([^"]+)" permlanes="([^"]+)"[^>]*modes="([^"]+)"')
_HWY = re.compile(r'osm:way:highway" class="java.lang.String">([^<]+)<')

def parse_car_links(net_path):
    """Yield dicts for every car link: id, length, freespeed(m/s), hwy, type, subcat.

    Streams the (possibly .gz) MATSim network. `type`/`subcat` come from classify().
    """
    opn = gzip.open if str(net_path).endswith(".gz") else open
    cur = None
    with opn(net_path, "rt") as f:
        for line in f:
            m = _LSTART.search(line)
            if m:
                cur = None
                if "car" in m.group(8).split(","):
                    cur = {"id": m.group(1), "length": float(m.group(4)),
                           "freespeed": float(m.group(5)), "cap": float(m.group(6)),
                           "hwy": ""}
                continue
            if cur is not None:
                hm = _HWY.search(line)
                if hm:
                    cur["hwy"] = hm.group(1)
                if "</link>" in line:
                    typ, sub = classify(cur["hwy"])
                    cur["type"], cur["subcat"] = typ, sub
                    yield cur
                    cur = None

def representative_v0(links):
    """Length-weighted mean base free speed (m/s) per (type,subcat) group.

    This is the paper's v^0 (Eqs 9-10): the default OSM unsaturated flow speed the
    period factor multiplies. Length weighting makes the group post-calibration mean
    land on the observed speed while preserving each link's relative speed limit.
    """
    num, den = {}, {}
    for l in links:
        if l["type"] is None:
            continue
        k = group_key(l["type"], l["subcat"])
        num[k] = num.get(k, 0.0) + l["freespeed"] * l["length"]
        den[k] = den.get(k, 0.0) + l["length"]
    return {k: num[k] / den[k] for k in num}
