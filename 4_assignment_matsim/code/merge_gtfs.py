#!/usr/bin/env python3
"""Merge the 5 MTA Maryland GTFS feeds (local-bus, light-rail, metro, MARC, commuter-bus) into a
single GTFS feed for pt2matsim, which maps one feed at a time. Each feed's identifiers are prefixed
with the feed name to avoid collisions, and all cross-references are rewritten consistently.

Output: data/gtfs_mta_merged.zip  (+ an unzipped folder)
"""
import zipfile, io, csv
from pathlib import Path
import pandas as pd

DATA = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim/data")
FEEDS = {"bus":"mta_local-bus.zip","lr":"mta_light-rail.zip","mt":"mta_metro.zip",
         "marc":"mta_marc.zip","cb":"mta_commuter-bus.zip"}
OUTDIR = DATA/"gtfs_mta_merged"; OUTDIR.mkdir(exist_ok=True)

# id columns to prefix per file, and the foreign keys that reference them
PREFIX_COLS = {
    "agency.txt":     ["agency_id"],
    "stops.txt":      ["stop_id","parent_station"],
    "routes.txt":     ["route_id","agency_id"],
    "trips.txt":      ["route_id","service_id","trip_id","shape_id","block_id"],
    "stop_times.txt": ["trip_id","stop_id"],
    "calendar.txt":   ["service_id"],
    "calendar_dates.txt":["service_id"],
    "shapes.txt":     ["shape_id"],
    "transfers.txt":  ["from_stop_id","to_stop_id"],
    "frequencies.txt":["trip_id"],
}
# files we carry into the merged feed (core + optional)
KEEP = list(PREFIX_COLS.keys())

def load(zf, name):
    if name not in zf.namelist(): return None
    with zf.open(name) as f:
        return pd.read_csv(io.TextIOWrapper(f, "utf-8-sig"), dtype=str, keep_default_na=False)

def main():
    merged = {k: [] for k in KEEP}
    for fid, fn in FEEDS.items():
        zf = zipfile.ZipFile(DATA/fn)
        for name in KEEP:
            df = load(zf, name)
            if df is None: continue
            for col in PREFIX_COLS[name]:
                if col in df.columns:
                    # prefix only non-empty values
                    df[col] = df[col].map(lambda v: f"{fid}:{v}" if v not in ("","nan") else v)
            df["_feed"] = fid
            merged[name].append(df)
        print(f"{fid:5s} ({fn}): " + ", ".join(f"{n.split('.')[0]}={len(load(zf,n))}" for n in ["stops.txt","routes.txt","trips.txt"] if load(zf,n) is not None))
    # feed_info / agency must exist; write merged tables
    for name, parts in merged.items():
        if not parts: continue
        out = pd.concat(parts, ignore_index=True).drop(columns=[c for c in ["_feed"] if True], errors="ignore")
        out.to_csv(OUTDIR/name, index=False, quoting=csv.QUOTE_MINIMAL)
    # zip it
    zpath = DATA/"gtfs_mta_merged.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in OUTDIR.iterdir():
            if f.suffix == ".txt": z.write(f, f.name)
    # summary
    print("\n=== merged feed ===")
    for name in ["agency.txt","stops.txt","routes.txt","trips.txt","stop_times.txt","calendar.txt","shapes.txt"]:
        p = OUTDIR/name
        if p.exists():
            print(f"  {name}: {sum(1 for _ in open(p))-1} rows")
    print(f"wrote {zpath}")

if __name__ == "__main__":
    main()
