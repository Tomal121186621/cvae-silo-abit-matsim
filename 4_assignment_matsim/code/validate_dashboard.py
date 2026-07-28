#!/usr/bin/env python3
"""Full base-year validation dashboard for a MATSim linkstats dump — the RIGHT metric suite to decide
whether the base is good enough (not just the volume bias ratio):
  VOLUME per tier: bias (Ssim/Sobs), GEH (% <5), R^2, %RMSE, n   + sim-vs-obs scatter (log-log, by tier)
  SPEED per tier & TOD: simulated congested speed (from linkstats travel times) vs the network's
    NPMRDS-calibrated free-flow speed (the observed reference baked into the speedcal network).
Usage: python3 validate_dashboard.py <linkstats.txt.gz> <out_prefix>
"""
import sys, gzip, numpy as np, pandas as pd
import xml.etree.ElementTree as ET
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
LS=sys.argv[1]; OUT=sys.argv[2] if len(sys.argv)>2 else "val_dashboard"
NET=f"{ROOT}/network_validation_2023/network_audit/bmr_network_pt_speedcal_localfix.xml.gz"
AADT=f"{ROOT}/network_validation_2023/transitfix/aadt/aadt_validation_2023_cleaned.csv"
SAMPLE=10.0
TIERCOL={"Interstate/Freeway":"#C0392B","Principal Arterial":"#E67E22","Minor Arterial":"#27AE60","Collector/Local":"#2E5C8A"}
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9})

# ---- linkstats: volume + (if present) travel time per link ----
ls=pd.read_csv(LS,sep="\t",low_memory=False,dtype={"LINK":str})
ls["vol24"]=pd.to_numeric(ls["HRS0-24avg"],errors="coerce")*SAMPLE
vol=dict(zip(ls["LINK"],ls["vol24"]))
def geh(m,o): return np.sqrt(2*(m-o)**2/(m+o)) if (m+o)>0 else np.nan

# ===== VOLUME validation vs AADT =====
df=pd.read_csv(AADT)
# stations with no matched network links can only ever score model=0 — exclude them
# (same treatment as the v7 mainline analysis) instead of letting them cap the tier bias
n_unmatched=int((df.link_ids.isna()|(df.n_links==0)).sum())
df=df[df.link_ids.notna()&(df.n_links>0)].copy()
print(f"[match] excluded {n_unmatched} stations with no matched links; {len(df)} scored")
df["m"]=df["link_ids"].apply(lambda s:sum(vol.get(l.strip(),0.0) for l in str(s).split(";") if l.strip()))
df=df[(df.obs_AADT>0)].copy()
df["geh"]=[geh(m,o) for m,o in zip(df.m,df.obs_AADT)]
G4=["Interstate/Freeway","Principal Arterial","Minor Arterial","Collector/Local"]
rows=[]
for g in G4+["ALL"]:
    s=df if g=="ALL" else df[df.facility==g]
    if not len(s): continue
    m,o=s.m.values,s.obs_AADT.values
    bias=m.sum()/o.sum()
    gp=100*(s.geh<5).mean()
    r2=np.corrcoef(m,o)[0,1]**2 if len(s)>2 and m.std()>0 else np.nan
    rmse=np.sqrt(((m-o)**2).mean()); prmse=100*rmse/o.mean()
    rows.append((g,len(s),bias,gp,r2,prmse))
vt=pd.DataFrame(rows,columns=["facility","n","bias","GEH<5%","R2","%RMSE"])
print("=== VOLUME validation ===")
print(vt.to_string(index=False,float_format=lambda x:f"{x:.3f}"))

# ===== SPEED: simulated congested vs NPMRDS-calibrated free-flow, by tier =====
# sim congested speed needs travel-time columns; detect them
ttcols=[c for c in ls.columns if "TRAVELTIME" in c.upper() and "24" in c and "avg" in c.lower()]
have_tt = len(ttcols)>0
speed_rows=[]
if have_tt:
    # parse network: link -> (length, freespeed_mph, hwy tier)
    TIER={"motorway":"Interstate/Freeway","motorway_link":"Interstate/Freeway","trunk":"Interstate/Freeway",
          "primary":"Principal Arterial","secondary":"Minor Arterial","tertiary":"Collector/Local","residential":"Collector/Local"}
    L={};FS={};HW={};node={}
    for _,el in ET.iterparse(gzip.open(NET,"rb"),events=("end",)):
        if el.tag=="link" and "car" in el.get("modes",""):
            hw=None
            for a in el.findall("attributes/attribute"):
                if a.get("name")=="osm:way:highway": hw=a.text;break
            L[el.get("id")]=float(el.get("length",0)); FS[el.get("id")]=float(el.get("freespeed",1))*2.237; HW[el.get("id")]=TIER.get(hw)
        el.clear()
    ttc=ttcols[0]; ls["tt24"]=pd.to_numeric(ls[ttc],errors="coerce")
    ls["simspd"]=[ (L.get(k,0)/tt*2.237) if tt and tt>0 else np.nan for k,tt in zip(ls.LINK,ls.tt24)]
    ls["ffspd"]=[FS.get(k,np.nan) for k in ls.LINK]; ls["tier"]=[HW.get(k) for k in ls.LINK]
    for g in G4:
        s=ls[(ls.tier==g)&(ls.vol24>0)&ls.simspd.notna()]
        if len(s): speed_rows.append((g,len(s),s.simspd.median(),s.ffspd.median()))
    print("\n=== SPEED (sim congested vs calibrated free-flow, mph) ===")
    for g,n,sim,ff in speed_rows: print(f"  {g:22s} n={n:5d}  sim {sim:5.1f}  free-flow {ff:5.1f}  ratio {sim/ff:.2f}")
else:
    print("\n[speed] linkstats has no TRAVELTIME columns (config writes volumes only) -> speed panel skipped")

# ===== PLOTS =====
fig,axs=plt.subplots(1,2 if speed_rows else 1,figsize=(13 if speed_rows else 7,6),squeeze=False)
ax=axs[0][0]
for g in G4:
    s=df[df.facility==g]
    ax.scatter(s.obs_AADT,s.m,s=10,c=TIERCOL[g],alpha=0.5,label=f"{g} (b={s.m.sum()/s.obs_AADT.sum():.2f}, GEH<5 {100*(s.geh<5).mean():.0f}%)")
lim=[100,3e5]; ax.plot(lim,lim,"k-",lw=0.8); ax.plot(lim,[1.15*l for l in lim],"k--",lw=0.5); ax.plot(lim,[0.85*l for l in lim],"k--",lw=0.5)
ax.set_xscale("log");ax.set_yscale("log");ax.set_xlim(lim);ax.set_ylim(lim)
ax.set_xlabel("Observed AADT 2023");ax.set_ylabel("Simulated daily volume (x10)")
ax.set_title(f"Volume: simulated vs observed by tier\n{LS.split('/')[-1]}",fontsize=10);ax.legend(fontsize=7,loc="upper left")
if speed_rows:
    ax2=axs[0][1]; x=np.arange(len(speed_rows)); w=0.38
    ax2.bar(x-w/2,[r[3] for r in speed_rows],w,label="free-flow (NPMRDS-calibrated)",color="#95a5a6")
    ax2.bar(x+w/2,[r[2] for r in speed_rows],w,label="simulated (congested, daily)",color="#2980b9")
    ax2.set_xticks(x);ax2.set_xticklabels([r[0].split("/")[0].split()[0] for r in speed_rows],fontsize=8)
    ax2.set_ylabel("speed (mph)");ax2.set_title("Speed: simulated vs calibrated free-flow by tier",fontsize=10);ax2.legend(fontsize=8)
fig.tight_layout(); fig.savefig(f"{OUT}.png",dpi=200,bbox_inches="tight")
vt.to_csv(f"{OUT}_volume_metrics.csv",index=False)
print(f"\nsaved {OUT}.png + {OUT}_volume_metrics.csv")
