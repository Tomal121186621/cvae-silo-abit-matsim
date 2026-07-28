#!/usr/bin/env python3
"""TRB/TRR per-attribute validation panels for Maryland, 2023 (calib5).

Light re-render only: loads ONE state (MD) + ONE year (2023) of ACS PUMS and the
calib5 SILO output, then calls the (restyled) valib.one_var_fig for each attribute.
Writes into validation/by_year_acs_calib5/TRB_figures/perattr_md_2023/.
"""
from __future__ import annotations
import os
from pathlib import Path
import numpy as np, pandas as pd

import valib as m
m.SCEN = Path("/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test"
              "/scenOutput/updated_vae_calib5/microData")
import trb_style; trb_style.apply()

YEAR = 2023
OUT = (Path(__file__).resolve().parents[1] / "validation" / "by_year_acs_calib5"
       / "TRB_figures" / "perattr_md_2023")
OUT.mkdir(parents=True, exist_ok=True)


def load_acs_md(year: int):
    """MD is fully in-region (coverage 1.0); recode ACS PUMS to the validation schema."""
    pdir = m.pums_dir(year); defl = m.CPI[2016] / m.CPI[year]
    h = m.read_pums_zip(pdir / "csv_hmd.zip",
                        ["SERIALNO", "WGTP", "NP", "VEH", "HINCP", "ADJINC", "BLD", "TYPE", "TYPEHUGQ"])
    tcol = "TYPEHUGQ" if "TYPEHUGQ" in h.columns else "TYPE"
    h = h[(pd.to_numeric(h[tcol], errors="coerce") == 1) & (pd.to_numeric(h["NP"], errors="coerce") >= 1)].copy()
    p = m.read_pums_zip(pdir / "csv_pmd.zip",
                        ["SERIALNO", "PWGTP", "AGEP", "SEX", "RAC1P", "HISP", "ESR", "SCHG", "PINCP", "ADJINC"])
    p = p[p["SERIALNO"].isin(set(h["SERIALNO"]))].copy()
    adj = pd.to_numeric(h["ADJINC"], errors="coerce").fillna(1e6)
    h["income"] = pd.to_numeric(h["HINCP"], errors="coerce").fillna(0) * adj / 1e6 * defl
    h["hhSize"] = pd.to_numeric(h["NP"], errors="coerce").clip(1, 7)
    h["autos"] = pd.to_numeric(h["VEH"], errors="coerce").fillna(0).clip(0, 3).astype(int)
    h["dwellingType"] = pd.to_numeric(h["BLD"], errors="coerce").fillna(2).astype(int).map(m.BLD_TO_TYPE).fillna(1).astype(int)
    h["hh_inc9"] = pd.cut(h["income"].astype(float), m.HH_INC_CUTS, labels=False, right=True).astype(int)
    h["w"] = pd.to_numeric(h["WGTP"], errors="coerce").fillna(0).clip(lower=0)
    adj = pd.to_numeric(p["ADJINC"], errors="coerce").fillna(1e6)
    p["income"] = pd.to_numeric(p["PINCP"], errors="coerce").fillna(0) * adj / 1e6 * defl
    p["age"] = pd.to_numeric(p["AGEP"], errors="coerce").clip(0, 99)
    p["age_bin"] = (p["age"] // 5).clip(0, 17).astype(int)
    p["gender"] = pd.to_numeric(p["SEX"], errors="coerce").clip(1, 2).astype(int)
    rac = pd.to_numeric(p["RAC1P"], errors="coerce").fillna(1).astype(int)
    hisp = pd.to_numeric(p["HISP"], errors="coerce").fillna(1).astype(int)
    p["race4"] = np.select([hisp > 1, rac == 1, rac == 2], ["hispanic", "white", "black"], default="other")
    esr = pd.to_numeric(p["ESR"], errors="coerce").fillna(6).astype(int)
    schg = pd.to_numeric(p["SCHG"], errors="coerce").fillna(0).astype(int); age = p["age"].to_numpy()
    p["occ_silo"] = np.select([age < 6, np.isin(esr, [1, 2, 4, 5]), schg > 0, esr == 3, (age >= 62) & (esr == 6)],
                              [0, 1, 3, 2, 4], default=2)
    p["w"] = pd.to_numeric(p["PWGTP"], errors="coerce").fillna(0).clip(lower=0)
    return h, p


def main():
    rh, rp = load_acs_md(YEAR)
    sh, sp = m.load_silo_year(YEAR)
    sh = sh[sh.state == "MD"]; sp = sp[sp.state == "MD"]
    n = 4  # continues the SILO figure numbering (heatmap=1, trajectory=2, md_year=3)
    for var, ttl in m.HH_VARS:
        cap = (f"Figure {n}. {ttl}, Maryland {YEAR}: SILO vs. ACS PUMS shares (top) and "
               f"signed per-bin gap with ±5 pp band (bottom).")
        tv = m.one_var_fig(OUT / f"hh_{var}.png", var, ttl, YEAR, sh[var], sh.w, rh[var], rh.w,
                           caption_text=cap)
        print(f"  hh {var}: TV={tv:.3f} -> {OUT/('hh_'+var+'.png')}"); n += 1
    for var, ttl in m.PP_VARS:
        if var not in sp.columns or var not in rp.columns:
            print(f"  skip pp {var}: column absent (SILO={var in sp.columns}, ACS={var in rp.columns})"); continue
        cap = (f"Figure {n}. {ttl}, Maryland {YEAR}: SILO vs. ACS PUMS shares (top) and "
               f"signed per-bin gap with ±5 pp band (bottom).")
        tv = m.one_var_fig(OUT / f"pp_{var}.png", var, ttl, YEAR, sp[var], sp.w, rp[var], rp.w,
                           caption_text=cap)
        print(f"  pp {var}: TV={tv:.3f} -> {OUT/('pp_'+var+'.png')}"); n += 1
    print("wrote MD-2023 per-attribute panels to", OUT)


if __name__ == "__main__":
    main()
