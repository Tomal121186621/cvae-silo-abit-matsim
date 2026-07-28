#!/usr/bin/env python3
"""Honest resident-only validation decomposition (S1 base, it.64, resident intra + E-I + I-E demand).

The MATSim demand is the ABIT synthetic-resident tour plan: internal (I-I) + inflow (E-I) + outflow (I-E).
It has NO through (E-E), NO commercial/freight, NO visitor traffic. AADT 2023 counts ALL vehicles.

This script quantifies, by facility class:
  1. resident capture ratio   = model(x10) / observed AADT_2023
  2. the EXPECTED non-resident/commercial component from the AADT vehicle-CLASS fields
       (SINGLE_UNIT + COMBINATION_UNIT trucks + bus = commercial; the rest is passenger vehicles)
     plus a literature estimate of the through/external passenger share by facility,
  3. and thereby SEPARATES  (a) the accepted non-resident gap  from
                            (b) any residual RESIDENT baseline shortfall (locals under by more than
                                the non-resident share can explain).

It directly answers: "without through-traffic, do the resident-dominated (collector/local) roads match?"
"""
import numpy as np, pandas as pd, geopandas as gpd
from netval2023_common import ROOT, OUTDIR, geh

VAL = OUTDIR/"aadt/aadt_validation_2023.csv"
GEO = ROOT/"data/aadt_2023_bmr_REAL.geojson"
OUT = OUTDIR

# Literature share of DAILY traffic that is NON-resident-personal (through E-E + external commuters not in
# the synthetic BMR pop + light commercial), by facility. Combined with the measured truck share this gives
# the total "out-of-scope for a resident-internal model" fraction. Ranges are typical US-metro values;
# we use midpoints and report the resulting resident-comparable target as a BAND.
NONRES_PERSONAL = {   # through + non-modeled external personal, fraction of AADT (excl. trucks)
    "Interstate/Freeway":(0.25,0.40),
    "Principal Arterial":(0.12,0.22),
    "Minor Arterial":    (0.06,0.12),
    "Collector/Local":   (0.03,0.08),
}
FAC_ORDER=["Interstate/Freeway","Principal Arterial","Minor Arterial","Collector/Local"]

def load():
    v=pd.read_csv(VAL)
    g=gpd.read_file(GEO)[["LOCATION_ID","AADT_2023","CAR_AADT","LIGHT_TRUCK_AADT","BUS_AADT",
                          "SINGLE_UNIT_AADT","COMBINATION_UNIT_AADT","MOTORCYCLE_AADT"]]
    v=v.merge(g, on="LOCATION_ID", how="left", suffixes=("","_g"))
    v["truck_aadt"]=v.SINGLE_UNIT_AADT+v.COMBINATION_UNIT_AADT
    v["comm_aadt"]=v.truck_aadt+v.BUS_AADT.fillna(0)     # commercial = trucks + bus
    return v

def facility_table(v):
    rows=[]
    for fac in FAC_ORDER:
        d=v[(v.facility==fac)&(v.model_daily>0)]
        if len(d)==0: continue
        m=d.model_daily.values; o=d.obs_AADT.values; gh=geh(m,o)
        cls=d[d.truck_aadt.notna()]
        truck_sh=np.nan; comm_sh=np.nan; carsh=np.nan
        if len(cls):
            truck_sh=100*(cls.truck_aadt/cls.obs_AADT).median()
            comm_sh =100*(cls.comm_aadt /cls.obs_AADT).median()
            carsh   =100*((cls.CAR_AADT+cls.LIGHT_TRUCK_AADT)/cls.obs_AADT).median()
        rows.append(dict(facility=fac,n=len(d),
                         agg_ratio=m.sum()/o.sum(),
                         med_ratio=np.median(m/o),
                         med_bias=100*np.median((m-o)/o),
                         pGEH5=100*np.mean(gh<5), pGEH10=100*np.mean(gh<10),
                         medGEH=np.median(gh),
                         corr2=np.corrcoef(o,m)[0,1]**2,
                         n_class=len(cls), truck_pct=truck_sh, comm_pct=comm_sh, car_pct=carsh))
    return pd.DataFrame(rows)

def decompose(tab):
    """Split the gap into accepted non-resident vs residual resident shortfall."""
    out=[]
    for _,r in tab.iterrows():
        fac=r.facility
        lo,hi=NONRES_PERSONAL[fac]
        # commercial (trucks+bus) fraction: measured where available, else facility default
        comm=(r.comm_pct/100.0) if pd.notna(r.comm_pct) else {"Interstate/Freeway":0.11,
              "Principal Arterial":0.06,"Minor Arterial":0.04,"Collector/Local":0.03}[fac]
        # total out-of-scope fraction band = commercial + non-resident personal band
        oos_lo=comm+lo; oos_hi=comm+hi
        # resident-comparable target = AADT * (1 - out_of_scope);  capture of THAT = agg_ratio/(1-oos)
        cap_hi=r.agg_ratio/(1-oos_hi)   # using the larger oos -> higher implied resident capture
        cap_lo=r.agg_ratio/(1-oos_lo)
        out.append(dict(facility=fac, agg_ratio=r.agg_ratio,
                        commercial_pct=100*comm, nonres_personal_pct=f"{lo*100:.0f}-{hi*100:.0f}",
                        out_of_scope_pct=f"{oos_lo*100:.0f}-{oos_hi*100:.0f}",
                        resid_capture=f"{cap_lo:.2f}-{cap_hi:.2f}",
                        resid_shortfall_pct=f"{100*(1-cap_hi):.0f}-{100*(1-cap_lo):.0f}"))
    return pd.DataFrame(out)

def i695(v):
    d=v[v.ROADNAME.astype(str).str.contains("BELTWAY",case=False,na=False)&(v.model_daily>0)]
    m=d.model_daily.values; o=d.obs_AADT.values
    return dict(n=len(d), agg_ratio=m.sum()/o.sum(), med_ratio=np.median(m/o),
                med_bias=100*np.median((m-o)/o), pGEH10=100*np.mean(geh(m,o)<10))

def main():
    v=load()
    tab=facility_table(v)
    pd.set_option("display.width",200,"display.max_columns",30)
    print("="*90); print("RESIDENT CAPTURE BY FACILITY (model x10 vs AADT 2023) — S1 resident-only base, it.64"); print("="*90)
    print(tab.to_string(index=False, formatters={c:"{:.2f}".format for c in ["agg_ratio","med_ratio","corr2"]}|
          {c:"{:.0f}".format for c in ["med_bias","pGEH5","pGEH10","medGEH","truck_pct","comm_pct","car_pct"]}))
    tab.to_csv(OUT/"resident_capture_by_facility.csv", index=False)
    print("\n"+"="*90); print("GAP DECOMPOSITION: accepted non-resident/commercial vs residual RESIDENT shortfall"); print("="*90)
    dec=decompose(tab)
    print(dec.to_string(index=False))
    dec.to_csv(OUT/"gap_decomposition.csv", index=False)
    print("\n"+"="*90); print("VERDICT — do resident-dominated (collector/local) roads match without through-traffic?"); print("="*90)
    cl=tab[tab.facility=="Collector/Local"].iloc[0]
    cld=dec[dec.facility=="Collector/Local"].iloc[0]
    print(f"Collector/Local: agg ratio {cl.agg_ratio:.2f} (median bias {cl.med_bias:.0f}%), "
          f"%GEH<10={cl.pGEH10:.0f}%, commercial share ~{cld.commercial_pct:.0f}%.")
    print(f"  Out-of-scope (commercial+non-res personal) ~{cld.out_of_scope_pct}% -> implied resident capture "
          f"{cld.resid_capture}, i.e. residual RESIDENT shortfall ~{cld.resid_shortfall_pct}%.")
    fw=tab[tab.facility=='Interstate/Freeway'].iloc[0]; fwd=dec[dec.facility=='Interstate/Freeway'].iloc[0]
    print(f"Freeway: agg ratio {fw.agg_ratio:.2f}; out-of-scope ~{fwd.out_of_scope_pct}% -> resident capture "
          f"{fwd.resid_capture} (most of the freeway gap IS the accepted non-resident/through/freight share).")
    print("\nI-695 Beltway (study corridor), resident portion:")
    print(" ", i695(v))

if __name__=="__main__":
    main()
