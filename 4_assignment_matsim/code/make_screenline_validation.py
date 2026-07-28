#!/usr/bin/env python3
"""Screenline validation for the Baltimore base — TRB publication style.

Six screenlines anchored on natural/structural barriers (standard practice: FHWA Model Validation
Manual — screenline totals within ±10% for major lines, ±20% for minor):
  A  Patapsco Harbor        the three tolled harbor crossings (water barrier)
  B  North line             E-W line north of the Beltway cutting the northern radials (I-83, I-795, ...)
  C  West line              N-S line west of the Beltway cutting the western radials (I-70, US-40, ...)
  D  South line             E-W line south of the Beltway cutting the Annapolis/DC radials (I-97, MD-2, MD-295, I-95S)
  E  East line              N-S line east of the city cutting the eastern radials (I-95NE, US-40E, ...)
  F  City cordon (Beltway)  radials crossing the I-695 ring (existing 14-station cordon)

Selection is GEOMETRIC: a QA'd AADT station belongs to a line if any of its matched network links
crosses the line segment. The script prints a capture audit (facilities + road names per line) so the
lines can be verified/tuned, draws the network map with screenlines + stations + labels, and produces
the per-line validation figure + CSV.

Usage: make_screenline_validation.py <linkstats.txt.gz> <out_dir>
"""
import sys, os, gzip
import numpy as np, pandas as pd
import xml.etree.ElementTree as ET
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

ROOT = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
LS, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
import os
AADT = os.environ.get("AADT_FILE", f"{ROOT}/network_validation_2023/transitfix/aadt/aadt_validation_2023_qa.csv")
NET  = f"{ROOT}/network_validation_2023/network_audit/bmr_network_pt_speedcal_capfix_v14kb.xml.gz"
plt.rcParams.update({
    "font.family":"serif","font.serif":["Times New Roman","Times","DejaVu Serif"],
    "mathtext.fontset":"stix","font.size":9,"axes.labelsize":9,"axes.titlesize":9,
    "xtick.labelsize":8,"ytick.labelsize":8,"legend.fontsize":7.5,
    "axes.spines.top":False,"axes.spines.right":False,"axes.linewidth":0.8})
def save(fig,name):
    fig.savefig(f"{OUT}/{name}.png",dpi=600,bbox_inches="tight")
    fig.savefig(f"{OUT}/{name}.pdf",bbox_inches="tight")
    plt.close(fig); print(f"  saved {name}")

# ---- screenline geometry (EPSG:26985 meters). Tuned so each cuts its radials once, off the Beltway. ----
SL = {
  "A  Patapsco Harbor":   None,   # link-set line: the three tolled crossings
  "B  North line":        ((412000, 197500), (447000, 197500)),
  "C  West line":         ((414500, 168000), (414500, 200000)),
  "D  South line":        ((405000, 158500), (450000, 158500)),
  "E  East line":         ((448500, 170000), (448500, 206000)),
}
SLCOL = {"A  Patapsco Harbor":"#D55E00","B  North line":"#0072B2","C  West line":"#009E73",
         "D  South line":"#CC79A7","E  East line":"#E69F00"}
HARBOR_LINKS = {'53478','41878','355067','373985','373989','236094','keybridge_eb','keybridge_wb'}
HARBOR_OBS = 226000.0   # FMT ~115k + BHT ~77k + KB ~34k (MDTA 2023)

def seg_cross(p1,p2,q1,q2):
    def ccw(a,b,c): return (c[1]-a[1])*(b[0]-a[0]) > (b[1]-a[1])*(c[0]-a[0])
    return ccw(p1,q1,q2)!=ccw(p2,q1,q2) and ccw(p1,p2,q1)!=ccw(p1,p2,q2)

# ---- network: node coords + link ends (car), tiers for the map ----
nodes={}; L={}
for _, el in ET.iterparse(gzip.open(NET,"rb"), events=("end",)):
    if el.tag=="node": nodes[el.get("id")]=(float(el.get("x")),float(el.get("y"))); el.clear(); continue
    if el.tag!="link": continue
    if "car" in el.get("modes",""):
        hw=None
        for a in el.findall("attributes/attribute"):
            if a.get("name")=="osm:way:highway": hw=a.text; break
        f=nodes.get(el.get("from")); t=nodes.get(el.get("to"))
        if f and t: L[el.get("id")]=(f,t,hw)
    el.clear()

# ---- volumes + stations ----
ls=pd.read_csv(LS,sep="\t",low_memory=False,dtype={"LINK":str})
vol=dict(zip(ls.LINK, pd.to_numeric(ls["HRS0-24avg"],errors="coerce")*10))
st=pd.read_csv(AADT)
st=st[st.link_ids.notna()&(st.n_links>0)&(st.obs_AADT>0)&(st.facility!="Ramp")].copy()
st["m"]=st.link_ids.apply(lambda s:sum(vol.get(l.strip(),0.0) for l in str(s).split(";") if l.strip()))

# ---- screenline mechanics (v2): the LINE cuts NETWORK links; each crossing road is paired to its
# AADT station via the shared OSM road name (station may sit anywhere along the road). Roads without
# a count station are excluded from BOTH sides (counted-coverage principle); coverage is reported.
# need names for links: reparse quickly for names of car links (major tiers only)
LN={}
for _, el in ET.iterparse(gzip.open(NET,"rb"), events=("end",)):
    if el.tag!="link": continue
    if "car" in el.get("modes",""):
        hw=None; nm=None
        for a in el.findall("attributes/attribute"):
            if a.get("name")=="osm:way:highway": hw=a.text
            elif a.get("name")=="osm:way:name": nm=a.text
        if hw in ("motorway","trunk","primary","secondary"):
            LN[el.get("id")]=(nm or f"unnamed_{hw}", hw)
    el.clear()
# station -> road name via its matched links' names
st["road"]=st.link_ids.apply(lambda s: next((LN[l.strip()][0] for l in str(s).split(";")
                                             if l.strip() in LN), None))
# station midpoint (first matched link) for nearest-selection
def st_mid(s):
    for l in str(s).split(";"):
        l=l.strip()
        if l in L: f,t,_=L[l]; return ((f[0]+t[0])/2,(f[1]+t[1])/2)
    return (np.nan,np.nan)
st[["sx","sy"]]=st.link_ids.apply(lambda s: pd.Series(st_mid(s)))

rows=[]; assign={}; details=[]
for name,seg in SL.items():
    if seg is None: continue
    q1,q2=seg
    # all major-tier car links crossing the line, grouped by road name
    groups={}
    for lid,(f,t,hw) in L.items():
        if lid not in LN: continue
        if seg_cross(f,t,q1,q2):
            rn=LN[lid][0]
            g=groups.setdefault(rn,{"model":0.0,"pts":[]})
            g["model"]+=vol.get(lid,0.0)
            g["pts"].append(((f[0]+t[0])/2,(f[1]+t[1])/2))
    hit=[]; obs_tot=0.0; mod_tot=0.0; uncounted=0.0
    for rn,g in groups.items():
        # design rule 1: a road crossing the line >2 times runs quasi-PARALLEL to it -> exclude
        # (its crossing volume is not a corridor flow through the line; e.g. MD-32 vs the south line)
        if len(g["pts"])>2 and rn!="unnamed_motorway":
            uncounted+=g["model"]; continue
        cx=np.mean([p[0] for p in g["pts"]]); cy=np.mean([p[1] for p in g["pts"]])
        cand=st[(st.road==rn)&st.sx.notna()]
        # design rule 2: the pairing station must represent the crossing -> within 8 km of it
        if len(cand): cand=cand[np.hypot(cand.sx-cx,cand.sy-cy)<8000]
        if len(cand)==0 or g["model"]<500:      # no station on this road (or negligible road)
            uncounted+=g["model"]; continue
        j=((cand.sx-cx)**2+(cand.sy-cy)**2).idxmin()
        r=st.loc[j]
        hit.append(dict(screenline=name,road=rn,station=r.LOCATION_ID,facility=r.facility,
                        obs=float(r.obs_AADT),model=round(g["model"]),x=cx,y=cy))
        obs_tot+=r.obs_AADT; mod_tot+=g["model"]
    assign[name]=pd.DataFrame(hit)
    details += hit
    cover=100*mod_tot/max(mod_tot+uncounted,1)
    rows.append(dict(screenline=name,n=len(hit),obs=int(obs_tot),model=int(mod_tot),
                     diff_pct=round(100*(mod_tot-obs_tot)/max(obs_tot,1),1),counted_cover_pct=round(cover,1)))
    print(f"\n{name}: {len(hit)} counted roads (coverage {cover:.0f}% of crossing volume)")
    for h in sorted(hit,key=lambda d:-d["obs"])[:12]:
        print(f"   {h['road'][:34]:34s} {h['facility'][:18]:18s} obs {h['obs']:8,.0f} model {h['model']:8,.0f}")
mh=sum(vol.get(l,0.0) for l in HARBOR_LINKS)
rows.insert(0,dict(screenline="A  Patapsco Harbor",n=3,obs=int(HARBOR_OBS),model=int(mh),
                   diff_pct=round(100*(mh-HARBOR_OBS)/HARBOR_OBS,1),counted_cover_pct=100.0))
sm=pd.DataFrame(rows); sm.to_csv(f"{OUT}/screenline_summary.csv",index=False)
pd.DataFrame(details).to_csv(f"{OUT}/screenline_stations.csv",index=False)
print("\n"+sm.to_string(index=False))

# ---- MAP: network + screenlines + stations + labels ----
fig,ax=plt.subplots(figsize=(7.2,7.2))
segs={"minor":[],"major":[],"mw":[]}
for lid,(f,t,hw) in L.items():
    if hw in ("motorway","motorway_link"): segs["mw"].append([f,t])
    elif hw in ("trunk","primary"): segs["major"].append([f,t])
    elif hw=="secondary": segs["minor"].append([f,t])
ax.add_collection(LineCollection(segs["minor"],colors="0.88",lw=0.25,zorder=1))
ax.add_collection(LineCollection(segs["major"],colors="0.72",lw=0.5,zorder=2))
ax.add_collection(LineCollection(segs["mw"],colors="0.45",lw=0.9,zorder=3))
for name,seg in SL.items():
    c=SLCOL[name]
    if seg is None:
        # harbor: draw a line through the three crossings
        ax.plot([434500,444500],[177500,171500],color=c,lw=2.2,ls="-",zorder=5)
        ax.annotate(name,xy=(444800,171200),color=c,fontsize=9,fontweight="bold")
        continue
    (x1,y1),(x2,y2)=seg
    ax.plot([x1,x2],[y1,y2],color=c,lw=2.2,zorder=5)
    ax.annotate(name,xy=(x2,y2),xytext=(x2+400,y2+400),color=c,fontsize=9,fontweight="bold")
    sub=assign[name]
    if len(sub):
        ax.plot(sub.x,sub.y,"o",ms=3.5,color=c,mec="white",mew=0.4,zorder=6,ls="none")
for l in HARBOR_LINKS:
    if l in L:
        f,t,_=L[l]; ax.plot((f[0]+t[0])/2,(f[1]+t[1])/2,"o",ms=4.5,color=SLCOL["A  Patapsco Harbor"],mec="white",mew=0.5,zorder=6)
# Interstate / major-road labels (EPSG:26985 data coords, angle follows the corridor)
ROADLBL = [
    ("I-95",   413800, 161000,  38), ("I-95",   445800, 192800,  40),
    ("I-695",  425600, 185300,  85), ("I-695",  444300, 175800, -60),
    ("I-83",   430700, 203800,  80), ("I-70",   411800, 182000,   0),
    ("I-795",  417600, 197400, -40), ("I-895",  434300, 172300,  30),
    ("I-97",   433900, 153800,  78), ("MD-295", 422600, 168300,  42),
    ("MD-100", 421500, 161300,   0),
]
for name, x, y, rot in ROADLBL:
    ax.text(x, y, name, fontsize=7.5, fontweight="bold", color="#333333",
            ha="center", va="center", rotation=rot, rotation_mode="anchor", zorder=7,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#999999", lw=0.5, alpha=0.85))
ax.set_xlim(408000,455000); ax.set_ylim(150000,212000); ax.set_aspect("equal")
ax.set_xlabel("Easting (m, EPSG:26985)"); ax.set_ylabel("Northing (m)")
ax.set_title("Screenline locations, AADT crossing stations, and the BMR network")
save(fig,"figS1_screenline_map")

# ---- per-line deviation vs FHWA screenline bands ----
fig,ax=plt.subplots(figsize=(5.6,3.2))
x=np.arange(len(sm))
ax.axhspan(-10,10,color="#c8e6c9",alpha=0.55,zorder=0)
ax.axhspan(-20,-10,color="#fff3c4",alpha=0.55,zorder=0); ax.axhspan(10,20,color="#fff3c4",alpha=0.55,zorder=0)
ax.axhline(0,color="0.3",lw=0.9)
cols=["#D55E00" if abs(r.diff_pct)>20 else "#0072B2" for r in sm.itertuples()]
ax.bar(x,sm.diff_pct,0.55,color=cols,zorder=3)
for xi,r in zip(x,sm.itertuples()):
    ax.text(xi,r.diff_pct+(1.5 if r.diff_pct>=0 else -1.5),f"{r.diff_pct:+.0f}%",
            ha="center",va="bottom" if r.diff_pct>=0 else "top",fontsize=7.5)
ax.set_xticks(x); ax.set_xticklabels([s.screenline.split("  ")[1] if "  " in s.screenline else s.screenline for s in sm.itertuples()],fontsize=7.5)
ax.set_ylabel("Simulated vs observed (%)")
ax.set_ylim(min(-48,sm.diff_pct.min()-8),max(28,sm.diff_pct.max()+8))
from matplotlib.patches import Patch
ax.legend(handles=[Patch(fc="#c8e6c9",label="FHWA ±10% (major screenline)"),
                   Patch(fc="#fff3c4",label="±20%")],frameon=False,fontsize=7,loc="lower left")
save(fig,"figS2_screenline_validation")
