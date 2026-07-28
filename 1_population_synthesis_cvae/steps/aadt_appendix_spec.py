#!/usr/bin/env python3
"""Shared spec for the v7 Base-Year AADT Validation appendix.
Reads the route/facility metrics CSV and returns one entry per appendix figure
(in presentation order), with the title, caption lines, and speaker narration all
derived from the CSV so the deck and the speaker guide stay in sync.
Numbers are read verbatim from the CSV — nothing is invented here.
"""
from __future__ import annotations
import csv
from pathlib import Path

# repo root = three levels up from this file (Updated VAE/steps/xxx.py)
ROOT = Path(__file__).resolve().parents[2]
V7 = ROOT / "Updated MATSim" / "network_validation_2023" / "v7_base"
CSV = V7 / "aadt_validation_by_route" / "route_validation_summary.csv"
BYROUTE = V7 / "aadt_validation_by_route"
BYFAC = V7 / "by_facility"

CAVEAT = ("corr² is squared Pearson (structure only); true R² penalizes level; GEH<5 is a strict hourly "
          "threshold on daily AADT — read the ±facility band + bias for daily fit. Freeways under-count = "
          "through+commercial scope; finest collectors = sparse 10%-sample assignment.")

# (fig filename, folder, csv level, csv key, road name, class label, tag)
ORDER = [
    # --- Interstates / Freeways (diagnostic) ---
    ("aadt_I95.png",  BYROUTE, "route", "I-95",   "I-95",   "Interstate", "diagnostic"),
    ("aadt_I695.png", BYROUTE, "route", "I-695",  "I-695 Baltimore Beltway", "Interstate", "diagnostic"),
    ("aadt_I895.png", BYROUTE, "route", "I-895",  "I-895 Harbor Tunnel Thruway", "Interstate", "diagnostic"),
    ("aadt_I70.png",  BYROUTE, "route", "I-70",   "I-70",   "Interstate", "diagnostic"),
    ("aadt_I83.png",  BYROUTE, "route", "I-83",   "I-83 Jones Falls Expwy", "Interstate", "diagnostic"),
    ("aadt_I97.png",  BYROUTE, "route", "I-97",   "I-97",   "Interstate", "diagnostic"),
    ("aadt_I795.png", BYROUTE, "route", "I-795",  "I-795 Northwest Expwy", "Interstate", "diagnostic"),
    ("aadt_MD295.png",BYROUTE, "route", "MD-295", "MD-295 Baltimore-Washington Pkwy", "Freeway", "diagnostic"),
    # --- Principal Arterials (validates) ---
    ("aadt_US1.png",  BYROUTE, "route", "US-1",   "US-1",   "Principal Arterial", "validates"),
    ("aadt_US40.png", BYROUTE, "route", "US-40",  "US-40 Pulaski Hwy", "Principal Arterial", "validates"),
    ("aadt_MD2.png",  BYROUTE, "route", "MD-2",   "MD-2 Ritchie Hwy", "Principal Arterial", "validates"),
    ("aadt_MD26.png", BYROUTE, "route", "MD-26",  "MD-26 Liberty Rd", "Principal Arterial", "validates"),
    ("aadt_MD45.png", BYROUTE, "route", "MD-45",  "MD-45 York Rd", "Principal Arterial", "validates"),
    ("aadt_MD140.png",BYROUTE, "route", "MD-140", "MD-140 Reisterstown Rd", "Principal Arterial", "validates"),
    ("aadt_MD144.png",BYROUTE, "route", "MD-144", "MD-144 Frederick Rd", "Principal Arterial", "validates"),
    ("aadt_MD139.png",BYROUTE, "route", "MD-139", "MD-139 Charles St", "Principal Arterial", "validates"),
    ("aadt_MD170.png",BYROUTE, "route", "MD-170", "MD-170 Camp Meade Rd", "Principal Arterial", "validates"),
    # --- Minor Arterials (validates) ---
    ("aadt_MD25.png", BYROUTE, "route", "MD-25",  "MD-25 Falls Rd", "Minor Arterial", "validates"),
    ("aadt_MD648.png",BYROUTE, "route", "MD-648", "MD-648 Baltimore-Annapolis Blvd", "Minor Arterial", "validates"),
    ("aadt_MD3.png",  BYROUTE, "route", "MD-3",   "MD-3 Crain Hwy", "Minor Arterial", "validates"),
    ("aadt_MD175.png",BYROUTE, "route", "MD-175", "MD-175 Annapolis Rd", "Minor Arterial", "validates"),
    ("aadt_MD97.png", BYROUTE, "route", "MD-97",  "MD-97 Georgia Ave", "Minor Arterial", "validates"),
    # --- Pooled ---
    ("aadt_MinorArterial(all).png",  BYROUTE, "route", "Minor Arterial (all)",  "Minor Arterial — pooled",  "Minor Arterial", "validates"),
    ("aadt_CollectorLocal(all).png", BYROUTE, "route", "Collector-Local (all)", "Collector / Local — pooled","Collector / Local", "diagnostic"),
    # --- FHWA facility tiers ---
    ("facility_Interstate.png",           BYFAC, "facility_tier", "Interstate",              "FHWA tier — Interstate",             "Interstate",              "diagnostic"),
    ("facility_OtherFreewayExpressway.png",BYFAC,"facility_tier", "Other Freeway-Expressway","FHWA tier — Other Freeway/Expressway","Other Freeway-Expressway","diagnostic"),
    ("facility_PrincipalArterial.png",    BYFAC, "facility_tier", "Principal Arterial",      "FHWA tier — Principal Arterial",     "Principal Arterial",      "validates"),
    ("facility_MinorArterial.png",        BYFAC, "facility_tier", "Minor Arterial",          "FHWA tier — Minor Arterial",         "Minor Arterial",          "validates"),
    ("facility_MajorCollector.png",       BYFAC, "facility_tier", "Major Collector",         "FHWA tier — Major Collector",        "Major Collector",         "diagnostic"),
    ("facility_MinorCollectorLocal.png",  BYFAC, "facility_tier", "Minor Collector-Local",   "FHWA tier — Minor Collector / Local","Minor Collector-Local",   "diagnostic"),
    # --- Aggregate + table ---
    ("aadt_ALL_mainline_loglog.png",       BYROUTE, "route", "ALL (mainline)", "All mainline stations (log-log)", "All facilities", "validates"),
    ("route_validation_summary_table.png", BYROUTE, "table", None,             "Route Validation Summary Table",  "reference",       "reference"),
]


def _rows():
    routes, facs = {}, {}
    with open(CSV, newline="") as f:
        for row in csv.DictReader(f):
            if row["level"] == "route":
                routes[row["route"]] = row
            elif row["level"] == "facility_tier":
                facs[row["route"]] = row
    return routes, facs


def _band_label(row):
    b = row["fac_band_pct"]
    return "within band" if b in ("-1", "-1.0") else f"within ±{b}% band"


def _metrics_line(row):
    return (f"n={row['n']} · corr²(>0)={row['corr2_simpos']} · true R²={row['R2_true']} · "
            f"GEH<5={row['GEH_lt5_pct']}% · {_band_label(row)}={row['within_facband_pct']}% · "
            f"median bias={row['median_bias_pct']}% · median ratio={row['median_ratio']}")


def _say(name, cls, tag, row):
    if tag == "validates":
        verdict = "This resident-scope facility VALIDATES"
    elif tag == "diagnostic":
        verdict = ("This panel is DIAGNOSTIC-scope — its under-count is the documented through+commercial "
                   "(freeway) or sparse 10%-sample (collector/local) scope, not a model error")
    else:
        verdict = "Reference table"
    return (f"{name} — a {cls.lower()}. {verdict}. Numbers: corr²(>0) {row['corr2_simpos']}, "
            f"true R² {row['R2_true']}, GEH<5 {row['GEH_lt5_pct']}%, {_band_label(row)} "
            f"{row['within_facband_pct']}%, median bias {row['median_bias_pct']}%, median ratio "
            f"{row['median_ratio']}, over n={row['n']} stations. Scope: {row['scope']}.")


def load():
    """Return list of appendix entries: dict(fig, title, cap_lines, say, tag)."""
    routes, facs = _rows()
    out = []
    for fn, folder, level, key, name, cls, tag in ORDER:
        fig = folder / fn
        title = f"{name} — {cls} [{tag}]"
        if level == "table" or key is None:
            cap_lines = ["Per-route / per-facility summary of every panel in this appendix: n, corr²(>0), "
                         "true R², GEH<5, ±facility band, median bias, median ratio, scope."]
            say = ("The summary table collects every route and facility panel in this appendix on one page — the "
                   "same columns used in each slide caption, so you can scan the whole validation at once.")
        else:
            row = routes[key] if level == "route" else facs[key]
            cap_lines = [_metrics_line(row), "Scope: " + row["scope"]]
            say = _say(name, cls, tag, row)
        out.append(dict(fig=fig, title=title, cap_lines=cap_lines, say=say, tag=tag))
    return out


if __name__ == "__main__":
    entries = load()
    print(f"{len(entries)} appendix figure entries")
    missing = [e["fig"] for e in entries if not e["fig"].exists()]
    for e in entries:
        mark = "OK " if e["fig"].exists() else "MISSING "
        print(mark, e["title"])
        for c in e["cap_lines"]:
            print("     ", c)
    print("MISSING:", len(missing))
