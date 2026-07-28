"""Stream ACS PUMS CSVs out of their state zips. Shared by analysis + preprocessing."""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Sequence

import pandas as pd

from . import config

__all__ = ["load_pums_zip", "load_all_states_raw"]


def _find_csv_in_zip(zf: zipfile.ZipFile) -> str:
    csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if not csvs:
        raise FileNotFoundError(f"No CSV in {zf.filename}")
    csvs.sort(key=lambda n: zf.getinfo(n).compress_size, reverse=True)
    return csvs[0]


def load_pums_zip(zip_path: Path, needed_cols: Sequence[str],
                  chunksize: int = 150_000) -> pd.DataFrame:
    """Read only `needed_cols` that exist in the file (robust across vintages)."""
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(f"Not found: {zip_path}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_name = _find_csv_in_zip(zf)
        with zf.open(csv_name) as f:
            header = f.readline().decode("utf-8", errors="replace")
        available = [c.strip().upper() for c in header.split(",")]
        use_cols = [c for c in needed_cols if c.upper() in available]
        dtype_hints = {"SERIALNO": str, "PUMA": str, "POWPUMA": str}
        dtype = {c: dtype_hints[c] for c in use_cols if c in dtype_hints}
        with zf.open(csv_name) as f:
            reader = pd.read_csv(f, usecols=use_cols, dtype=dtype, chunksize=chunksize,
                                 low_memory=True, encoding="utf-8", on_bad_lines="skip")
            chunks = [c.rename(columns=str.upper) for c in reader]
    if not chunks:
        return pd.DataFrame(columns=[c.upper() for c in use_cols])
    return pd.concat(chunks, ignore_index=True)


def load_all_states_raw(hh_cols, pp_cols):
    """Load raw (un-recoded) HH and PP frames for all MSTM states, tagging state."""
    H, P = [], []
    for fips in config.MSTM_STATE_FIPS:
        ab = config.STATE_FIPS_ABBREV[fips].lower()
        hz = config.PUMS_DIR / f"csv_h{ab}.zip"
        pz = config.PUMS_DIR / f"csv_p{ab}.zip"
        if not hz.exists():
            print(f"  skip {ab.upper()}: missing {hz.name}")
            continue
        h = load_pums_zip(hz, hh_cols); h["ST"] = config.STATE_FIPS_ABBREV[fips]
        p = load_pums_zip(pz, pp_cols); p["ST"] = config.STATE_FIPS_ABBREV[fips]
        H.append(h); P.append(p)
        print(f"  loaded {ab.upper()}: {len(h):,} HH / {len(p):,} PP", flush=True)
    return pd.concat(H, ignore_index=True), pd.concat(P, ignore_index=True)
