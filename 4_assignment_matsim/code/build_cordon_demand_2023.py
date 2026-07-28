#!/usr/bin/env python3
"""Build the 2023 cordon external/through + truck background demand for the BMR MATSim base.

The resident ABIT population makes only internal trips, so the freeways are under-assigned ~2.5x
(freeway mainline bias -61%). This adds the missing background traffic:

  * EXTERNAL / THROUGH (E-E) : vehicles that enter one freeway gateway and leave at another
                               (I-95 S <-> NE corridor dominates). Distributed gateway->gateway by gravity.
  * EXTERNAL-INTERNAL (E-I)  : vehicles with one end outside, one interior end (sampled from resident
                               activity coords, an attraction proxy).
  * TRUCKS                   : tagged (vehType=truck) share of freeway crossings, concentrated on the
                               high-truck freight gateways (I-95, I-70, I-83) via the AADT class fields.

Gateways are detected as the motorway/trunk links that cross the BMR boundary (validation/gis/bmr_boundary.gpkg),
which reproduces validation/gis/cordon_gateways.gpkg. Cordon closure is EXACT by construction:
external_g = observed cordon AADT_2023 - current model crossings at gateway g (from the base it.64 linkstats).
The E-E vs E-I split (THROUGH_FRAC) is the interior-loading lever, CALIBRATED against interior interstate
screenlines via a free-flow all-or-nothing pre-assignment (scipy dijkstra) so internal freeway counts close.

Departure times follow the TMAS 2023 weekday interstate hourly profile. Demand is generated at the 10%
sample (x10 convention) and appended to the base plans.

Usage:
  python build_cordon_demand_2023.py diagnose            # gateways + calibrate THROUGH_FRAC, no plans
  python build_cordon_demand_2023.py write [THROUGH_FRAC] [SCALE]   # write cordon + combined plans
"""
import sys, gzip, math, glob
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import Point
from shapely.prepared import prep
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, str(Path(__file__).parent))
import netval2023_common as N

ROOT = N.ROOT
BOUND = ROOT/"validation/gis/bmr_boundary.gpkg"
AADT_FILE = ROOT/"data/aadt_2023_bmr_REAL.geojson"
AADTVAL   = ROOT/"network_validation_2023/aadt/aadt_validation_2023.csv"
BASE_POP = ROOT/"scenarios/01_base_no_pricing/input/matsim_population_abit_bmr.xml.gz"
ACT_CSV  = ROOT/"scenarios/01_base_no_pricing/output/output_trips.csv.gz"
OUT_CORDON = ROOT/"scenarios/01_base_no_pricing/input/cordon_background_2023.xml.gz"
OUT_COMBINED = ROOT/"scenarios/01_base_no_pricing/input/matsim_population_combined_2023.xml.gz"
CALIB = ROOT/"network_validation_2023/calibration"

SAMPLE = 0.10                 # 10% sample -> x10 (matches resident pop / flowCapFactor 0.10)
DIST_POWER = 2.0             # through distribution weight ~ dist^POWER: favours long/opposite (corridor) moves
GATEWAY_CLUSTER = 1500.0      # m: cluster crossing links into one physical gateway
DEFAULT_TRUCK = {"IS":0.092, "US":0.031, "OTHER":0.02}
MAJORS = {"motorway","trunk","motorway_link","trunk_link"}
RNG = np.random.default_rng(20230703)

# Curated cordon-AADT corrections for major motorway corridors where the boundary AADT point is a ramp or
# a mis-snapped surface street (interstate mainline is sparsely instrumented at the network edge). Keyed by
# rounded gateway (cx,cy); value = both-direction cordon AADT_2023 read from the nearest true mainline point.
CORDON_FIX = {
    (476612,212730): (78960, "I-95 NE / JFK Mem Hwy (mainline, ramp-only at edge)"),
    (414585,155694): (90000, "MD-295 Balt-Wash Pkwy (mainline ~106k interior, boundary ~90k)"),
    (385424,187586): (55000, "I-70 W at Mt Airy (interchange ramps only at edge)"),
}

# ------------------------------------------------------------------- known mis-tagged freeway gateways
# ROOT CAUSE (I-83 miss): the crossing detector (build_gateways) keeps only links whose osm:way:highway is in
# MAJORS = {motorway,trunk,motorway_link,trunk_link}. On I-83 (Harrisburg Expwy) at the northern cordon
# (PA state line, y~228000, x~429.4k) the MATSim/OSM network DOWNGRADES the interstate mainline to hwy=
# "primary" (freespeed ~50 mph, cap 1500) -- the motorway-class portion truncates ~4 km inside the cordon
# (ends ~y224500, BOTH nodes inside), so no motorway/trunk link has one node in and one out near I-83, and
# the crossing is carried by the primary pair 270722/270723. The SAME mis-tag makes the AADT matcher miss it
# (interstate F_SYSTEM=1 requires motorway/trunk), so I-83 boundary stations B1186/B1187 have model_daily=0.
# Broadening MAJORS to include "primary" would flood the cordon with dozens of spurious arterial gateways
# and the primary link is indistinguishable from a true arterial by freespeed/capacity, so a clean automatic
# detection fix is fragile. Instead we RE-INJECT the known mis-tagged freeway crossing(s) explicitly here, and
# let the normal code path compute cur_vol (it.64 linkstats) and external = cordon_aadt - cur_vol. Reproducible.
# Each entry uses the actual boundary-crossing link pair (inbound=in_lid, outbound=out_lid) on the freeway
# alignment; cordon_aadt is the nearest true mainline boundary station (I-83: B1186 = 42130 AADT, on the
# cordon at y~228119 -- NOT the 54k/58k/128k interior stations that pick up local traffic further south).
KNOWN_MISSED_GATEWAYS = [
    dict(cx=429422.3221365507, cy=227977.72028384078, hwy="motorway",
         in_lid="270722", in_tnode=37724948, out_lid="270723", out_fnode=37724948,
         lids=["270722", "270723"], snap_d=241.81, cordon_aadt=42130.0,
         road="I-83 (Harrisburg Expwy)", prefix="IS", truck_frac=0.092),
]

def add_known_missed_gateways(res):
    """Append hand-verified freeway gateways the crossing detector missed (mis-tagged non-motorway/trunk).
    Returns res with the extra rows; cur_vol/external are filled by the caller's standard path."""
    if not KNOWN_MISSED_GATEWAYS:
        return res
    have=set(res["road"].astype(str))
    extra=[g for g in KNOWN_MISSED_GATEWAYS if g["road"] not in have]
    if not extra:
        return res
    add=pd.DataFrame(extra)
    print(f"  + re-injecting {len(add)} known mis-tagged freeway gateway(s): {list(add.road)}")
    return pd.concat([res, add], ignore_index=True)

# --------------------------------------------------------------------- network + graph
def build_network():
    nodes, links = N.parse_network()
    ls = N.load_linkstats()
    nid = {n:i for i,n in enumerate(nodes)}
    coords = np.array([nodes[n] for n in nodes])
    u=[]; v=[]; w=[]; edge_link={}; linkinfo={}
    for l in links:
        if l["from"] not in nid or l["to"] not in nid: continue
        a=nid[l["from"]]; b=nid[l["to"]]
        ax,ay=nodes[l["from"]]; bx,by=nodes[l["to"]]
        length=math.hypot(bx-ax,by-ay) or 1.0
        fs=max(l["freespeed"],1.0)
        u.append(a); v.append(b); w.append(length/fs)
        edge_link[(a,b)]=l["id"]
        vol=float(ls.loc[l["id"],"vol24"]) if l["id"] in ls.index else 0.0
        linkinfo[l["id"]]={"from":a,"to":b,"fx":ax,"fy":ay,"tx":bx,"ty":by,
                           "hwy":l["hwy"],"vol24":vol,"length":length}
    G=csr_matrix((w,(u,v)), shape=(len(nodes),len(nodes)))
    return dict(nodes=nodes,nid=nid,coords=coords,linkinfo=linkinfo,edge_link=edge_link,G=G,ls=ls,links=links)

# --------------------------------------------------------------------- gateways from boundary crossings
def build_gateways(net):
    nodes=net["nodes"]; linkinfo=net["linkinfo"]
    b=gpd.read_file(BOUND).geometry.iloc[0]; pb=prep(b)
    inside={n:pb.contains(Point(xy)) for n,xy in nodes.items()}
    recs=[]
    idx2node={i:n for n,i in net["nid"].items()}
    for lid,li in linkinfo.items():
        if li["hwy"] not in MAJORS: continue
        fn=idx2node[li["from"]]; tn=idx2node[li["to"]]
        fi=inside[fn]; ti=inside[tn]
        if fi==ti: continue
        recs.append({"lid":lid,"mx":(li["fx"]+li["tx"])/2,"my":(li["fy"]+li["ty"])/2,
                     "hwy":li["hwy"],"inbound":(not fi and ti),
                     "fnode":li["from"],"tnode":li["to"]})
    df=pd.DataFrame(recs)
    used=np.zeros(len(df),bool); xy=df[["mx","my"]].values; clusters=[]
    for i in range(len(df)):
        if used[i]: continue
        d=np.hypot(xy[:,0]-xy[i,0],xy[:,1]-xy[i,1]); m=(d<GATEWAY_CLUSTER)&(~used); used|=m
        sub=df[m]; inb=sub[sub.inbound]; outb=sub[~sub.inbound]
        clusters.append({"cx":sub.mx.mean(),"cy":sub.my.mean(),"hwy":sub.hwy.mode().iloc[0],
            "in_lid": inb.lid.iloc[0] if len(inb) else None,
            "in_tnode": int(inb.tnode.iloc[0]) if len(inb) else None,
            "out_lid": outb.lid.iloc[0] if len(outb) else None,
            "out_fnode": int(outb.fnode.iloc[0]) if len(outb) else None,
            "lids": list(sub.lid)})
    return pd.DataFrame(clusters)

def attach_cordon_aadt(gwc):
    a=gpd.read_file(AADT_FILE).to_crs(N.CRS); a=a[a.AADT_2023>0].copy()
    ax=a.geometry.x.values; ay=a.geometry.y.values
    out=[]
    for _,g in gwc.iterrows():
        d=np.hypot(ax-g.cx, ay-g.cy); j=int(np.argmin(d)); near=a.iloc[j]
        aadt=float(near.AADT_2023)
        pref=near.ID_PREFIX if near.ID_PREFIX in ("IS","US") else "OTHER"
        if pd.notna(near.SINGLE_UNIT_AADT) and pd.notna(near.COMBINATION_UNIT_AADT) and aadt>0:
            tf=float(near.SINGLE_UNIT_AADT+near.COMBINATION_UNIT_AADT)/aadt
        else:
            tf=DEFAULT_TRUCK.get(pref,0.02)
        out.append({"snap_d":d[j],"cordon_aadt":aadt,"road":near.ROADNAME,
                    "prefix":near.ID_PREFIX,"truck_frac":min(tf,0.4)})
    res=pd.concat([gwc.reset_index(drop=True), pd.DataFrame(out)], axis=1)
    # apply curated corrections
    for i,g in res.iterrows():
        key=(round(g.cx/50)*50, round(g.cy/50)*50)
        for (fx,fy),(val,note) in CORDON_FIX.items():
            if abs(g.cx-fx)<800 and abs(g.cy-fy)<800:
                res.at[i,"cordon_aadt"]=float(val); res.at[i,"road"]=note
                if val>0 and res.at[i,"prefix"] not in ("IS","US"):
                    res.at[i,"truck_frac"]=DEFAULT_TRUCK["IS"] if "I-" in note else res.at[i,"truck_frac"]
    return res

def current_gateway_vol(g, ls):
    return sum(float(ls.loc[lid,"vol24"]) for lid in g["lids"] if lid in ls.index)

# --------------------------------------------------------------------- gravity + preassign
def furness(entries, exits, gwxy, iters=80):
    """Doubly-constrained distribution. Through traffic = LONG cross-region moves, so the deterrence
    FAVOURS far/opposite gateway pairs (weight ~ dist^DIST_POWER): I-95 SW<->NE, US-50<->US-301, etc."""
    n=len(entries); D=np.zeros((n,n))
    for i in range(n):
        for j in range(n):
            if i==j: continue
            dist=math.hypot(gwxy[i][0]-gwxy[j][0], gwxy[i][1]-gwxy[j][1])
            D[i,j]=(dist/1000.0)**DIST_POWER
    T=D.copy()
    for _ in range(iters):
        rs=T.sum(1); rs[rs==0]=1; T*=(entries/rs)[:,None]
        cs=T.sum(0); cs[cs==0]=1; T*=(exits/cs)[None,:]
    return T

def preassign(T, gwc, net):
    """All-or-nothing free-flow assignment of gateway OD matrix T -> per-link volume dict."""
    nid=net["nid"]; G=net["G"]; linkinfo=net["linkinfo"]
    idx2node={i:n for n,i in nid.items()}
    n=len(gwc)
    src=[g.in_tnode if g.in_tnode is not None else -1 for _,g in gwc.iterrows()]
    tgt=[g.out_fnode if g.out_fnode is not None else -1 for _,g in gwc.iterrows()]
    valid_src=[s for s in src if s>=0]
    dist,pred=dijkstra(G, directed=True, indices=valid_src, return_predecessors=True)
    srow={s:k for k,s in enumerate(valid_src)}
    # build (u,v)->linkid once
    linkvol={}
    entry_lids={g.in_lid for _,g in gwc.iterrows() if g.in_lid}
    exit_lids ={g.out_lid for _,g in gwc.iterrows() if g.out_lid}
    for i in range(n):
        s=src[i]
        if s<0 or s not in srow: continue
        k=srow[s]; prow=pred[k]
        for j in range(n):
            if i==j or T[i,j]<=0: continue
            t=tgt[j]
            if t<0 or not np.isfinite(dist[k,t]): continue
            vol=T[i,j]; cur=t
            while cur!=s and cur>=0:
                p=prow[cur]
                if p<0: break
                lid=net["edge_link"].get((p,cur))
                if lid is not None: linkvol[lid]=linkvol.get(lid,0.0)+vol
                cur=p
        # add the entry & exit gateway links themselves for the OD row/col
    # add entry/exit gateway link volumes (each carries its marginal)
    for i,(_,g) in enumerate(gwc.iterrows()):
        if g.in_lid:  linkvol[g.in_lid]  = linkvol.get(g.in_lid,0.0)  + T[i,:].sum()
        if g.out_lid: linkvol[g.out_lid] = linkvol.get(g.out_lid,0.0) + T[:,i].sum()
    return linkvol

# --------------------------------------------------------------------- interior screenline calibration
def interior_screenlines(gwc):
    """Interior interstate mainline stations (from base validation), away from gateways."""
    v=pd.read_csv(AADTVAL)
    v=v[(v.ID_PREFIX=="IS")&(v.model_daily>0)&(v.link_ids.notna())].copy()
    gxy=gwc[["cx","cy"]].values
    keep=[]
    # station lon/lat are network coords already? validate uses lon/lat = geometry.x/.y in CRS 26985
    for _,s in v.iterrows():
        d=np.hypot(gxy[:,0]-s.lon, gxy[:,1]-s.lat).min()
        keep.append(d>N.__dict__.get("NEAR",6000.0) if False else d>6000.0)
    v=v[pd.Series(keep,index=v.index)]
    return v

def calibrate_through_frac(gwc, net, ee_unit_vol, ei_unit_vol):
    """Pick THROUGH_FRAC so interior IS screenlines close. model = resident + phi*EE + (1-phi)*EI."""
    scr=interior_screenlines(gwc)
    obs=scr.obs_AADT.values; res=scr.model_daily.values
    def link_sum(lv, ids): return sum(lv.get(l,0.0) for l in ids.split(";"))
    ee=np.array([link_sum(ee_unit_vol,ids) for ids in scr.link_ids])
    ei=np.array([link_sum(ei_unit_vol,ids) for ids in scr.link_ids])
    best=None
    for phi in np.linspace(0.0,1.0,21):
        model=res+phi*ee+(1-phi)*ei
        ratio=model.sum()/obs.shape and model.sum()/obs.sum()
        g=N.geh(model,obs); medgeh=np.nanmedian(g)
        score=abs(np.log(model.sum()/obs.sum()))
        if best is None or score<best[0]: best=(score,phi,model.sum()/obs.sum(),medgeh)
    return scr, best

# --------------------------------------------------------------------- E-I destinations
def interior_activity_pool(nmax=40000):
    """Sample interior activity coordinates from resident trips (attraction proxy)."""
    t=pd.read_csv(ACT_CSV, sep=";", usecols=["end_x","end_y","end_activity_type"])
    t=t.dropna(subset=["end_x","end_y"])
    if len(t)>nmax: t=t.sample(nmax, random_state=7)
    return t[["end_x","end_y"]].values

# ---------------------------------------------------------- internal freeway uplift (ODME)
MIN_INTERNAL_KM = 12.0        # only clone LONG resident car trips (these self-select onto freeways)

def load_long_car_trips():
    """Long resident car trips (O/D coords) — the freeway-using subset to clone for the internal uplift."""
    t=pd.read_csv(ACT_CSV, sep=";",
                  usecols=["main_mode","traveled_distance","start_x","start_y","end_x","end_y"])
    t=t[(t.main_mode=="car") & (t.traveled_distance>=MIN_INTERNAL_KM*1000)].dropna(
        subset=["start_x","start_y","end_x","end_y"])
    return t[["start_x","start_y","end_x","end_y"]].values   # full-scale count = len(t)*10

def preassign_internal(od_sample, net, want_link_ids, nsrc_cap=800):
    """Free-flow assign a sample of internal O-D; return interior-link volume contributed by the
    FULL long-trip set (scaled up from the sample). Used to calibrate the clone fraction."""
    from scipy.spatial import cKDTree
    nid=net["nid"]; G=net["G"]; coords=net["coords"]
    idx_all=np.arange(len(coords))
    tree=cKDTree(coords)
    _,o_nodes=tree.query(od_sample[:,0:2]); _,d_nodes=tree.query(od_sample[:,2:4])
    uniq=np.unique(o_nodes)
    if len(uniq)>nsrc_cap:
        sel=RNG.choice(len(uniq), size=nsrc_cap, replace=False); uniq=uniq[sel]
        mask=np.isin(o_nodes, uniq); o_nodes=o_nodes[mask]; d_nodes=d_nodes[mask]
    dist,pred=dijkstra(G, directed=True, indices=uniq, return_predecessors=True)
    srow={s:k for k,s in enumerate(uniq)}
    want=set(want_link_ids)
    lv={}
    used=0
    for o,d in zip(o_nodes,d_nodes):
        if o not in srow or o==d: continue
        k=srow[o]
        if not np.isfinite(dist[k,d]): continue
        used+=1; cur=d; prow=pred[k]
        while cur!=o and cur>=0:
            p=prow[cur]
            if p<0: break
            lid=net["edge_link"].get((p,cur))
            if lid in want: lv[lid]=lv.get(lid,0.0)+1.0
            cur=p
    # scale sample -> full long-trip set at x10 (each sampled trip represents (Ntot*10/used) full trips)
    return lv, used

# --------------------------------------------------------------------- plan writing
def emit_agent(w, aid, o_link, ox, oy, d_link, dx, dy, dep, is_truck):
    # NOTE: no "subpopulation" attribute — that would require a per-subpopulation replanning strategy
    # (RunBaltimore defines strategies only for the default subpopulation). Background agents are
    # identifiable by the "bg_" id prefix and the vehType attribute below.
    w.write(f'  <person id="{aid}">\n')
    w.write('    <attributes>\n')
    w.write(f'      <attribute name="vehType" class="java.lang.String">{"truck" if is_truck else "car"}</attribute>\n')
    w.write('    </attributes>\n')
    w.write('    <plan selected="yes">\n')
    olink=f' link="{o_link}"' if o_link else ""
    dlink=f' link="{d_link}"' if d_link else ""
    w.write(f'      <activity type="other"{olink} x="{ox:.1f}" y="{oy:.1f}" end_time="{dep}"/>\n')
    w.write('      <leg mode="car"/>\n')
    w.write(f'      <activity type="other"{dlink} x="{dx:.1f}" y="{dy:.1f}"/>\n')
    w.write('    </plan>\n  </person>\n')

def tmas_interstate_profile():
    """Weekday interstate hourly share (normalised 24-vec) from TMAS 2023."""
    from netval2023_common import CRS
    HRS=[f"hour_{h:02d}" for h in range(24)]
    sta=pd.read_csv(STA_PATH(), sep="|", dtype=str)
    sta["fs"]=sta.f_system.str[0].astype(int)
    is_st=set(sta[sta.fs.isin([1,2])].station_id)
    prof=np.zeros(24); wk={"2","3","4","5","6"}
    for f in sorted(glob.glob(VOLGLOB())):
        v=pd.read_csv(f, sep="|", dtype=str)
        v=v[v.day_of_week.isin(wk) & v.station_id.isin(is_st)]
        for h in range(24): prof[h]+=pd.to_numeric(v[HRS[h]],errors="coerce").fillna(0).sum()
    return prof/prof.sum() if prof.sum()>0 else np.ones(24)/24

def STA_PATH(): return str(ROOT/"data/tmas_2023/MD_2023 (TMAS).STA")
def VOLGLOB():  return str(ROOT/"data/tmas_2023/md_vol/*.VOL")

def sample_departures(ntrips, prof):
    hours=RNG.choice(24, size=ntrips, p=prof)
    mins=RNG.integers(0,3600,size=ntrips)
    return hours*3600+mins+1

# --------------------------------------------------------------------- main build
def build_matrices(gwc, net, through_frac):
    gwxy=gwc[["cx","cy"]].values
    ext=gwc["external"].values
    # E-E marginals
    ee_ent=through_frac*ext/2.0; ee_ext=through_frac*ext/2.0
    T_ee=furness(ee_ent, ee_ext, gwxy)
    # E-I marginals (per gateway inbound + outbound half)
    ei_in=(1-through_frac)*ext/2.0   # entering -> interior
    ei_out=(1-through_frac)*ext/2.0  # interior -> exiting
    return T_ee, ei_in, ei_out

def unit_matrices(gwc, net):
    """EE and EI pre-assignment link volumes for phi=1 (EE) and phi=0 (EI), for calibration."""
    gwxy=gwc[["cx","cy"]].values; ext=gwc["external"].values
    T_ee=furness(ext/2.0, ext/2.0, gwxy)
    ee_vol=preassign(T_ee, gwc, net)
    # EI unit: each gateway sends ext/2 into interior along freeway; approximate its link loading by
    # assigning gateway-> a set of interior IS screenline nodes near the region core (all-or-nothing to core).
    ei_vol=preassign_ei(ext/2.0, ext/2.0, gwc, net)
    return ee_vol, ei_vol

def preassign_ei(ei_in, ei_out, gwc, net):
    """E-I loads the freeway from each gateway toward the region core and back (half-corridor)."""
    nid=net["nid"]; G=net["G"]; coords=net["coords"]
    core=coords.mean(0)
    core_node=int(np.argmin(np.hypot(coords[:,0]-core[0], coords[:,1]-core[1])))
    n=len(gwc)
    src=[g.in_tnode if g.in_tnode is not None else -1 for _,g in gwc.iterrows()]
    valid=[s for s in src if s>=0]
    dist,pred=dijkstra(G, directed=True, indices=valid, return_predecessors=True)
    srow={s:k for k,s in enumerate(valid)}
    lv={}
    for i in range(n):
        s=src[i]
        if s<0 or s not in srow: continue
        k=srow[s]; prow=pred[k]; t=core_node; vol=ei_in[i]
        if not np.isfinite(dist[k,t]): continue
        cur=t
        while cur!=s and cur>=0:
            p=prow[cur]
            if p<0: break
            lid=net["edge_link"].get((p,cur))
            if lid: lv[lid]=lv.get(lid,0.0)+vol
            cur=p
    # outbound symmetric (core->gateway) approximated as same links, add ei_out
    for i in range(n):
        s=src[i]
        if s<0 or s not in srow: continue
        k=srow[s]; prow=pred[k]; t=core_node; vol=ei_out[i]
        if not np.isfinite(dist[k,t]): continue
        cur=t
        while cur!=s and cur>=0:
            p=prow[cur]
            if p<0: break
            lid=net["edge_link"].get((p,cur))
            if lid: lv[lid]=lv.get(lid,0.0)+vol
            cur=p
    return lv

def linkxy(net, lid):
    li=net["linkinfo"][lid]; return (li["fx"]+li["tx"])/2,(li["fy"]+li["ty"])/2

def write_plans(gwc, net, through_frac, scale, clone_frac):
    prof=tmas_interstate_profile()
    pool=interior_activity_pool()
    T_ee, ei_in, ei_out = build_matrices(gwc, net, through_frac)
    T_ee*=scale; ei_in*=scale; ei_out*=scale
    gwxy=gwc[["cx","cy"]].values
    n=len(gwc)
    # gather all trips as (o_link,ox,oy,d_link,dx,dy,truck_prob)
    trips=[]
    # E-E through
    for i in range(n):
        gi=gwc.iloc[i]
        if not gi.in_lid: continue
        oxy=linkxy(net,gi.in_lid)
        for j in range(n):
            if i==j: continue
            gj=gwc.iloc[j]
            if not gj.out_lid: continue
            cnt=T_ee[i,j]*SAMPLE
            k=int(cnt)+ (1 if RNG.random()<(cnt-int(cnt)) else 0)
            if k<=0: continue
            dxy=linkxy(net,gj.out_lid)
            tp=gi.truck_frac
            for _ in range(k):
                trips.append((gi.in_lid,oxy[0],oxy[1],gj.out_lid,dxy[0],dxy[1],tp))
    # E-I: gateway -> interior (in) and interior -> gateway (out)
    for i in range(n):
        gi=gwc.iloc[i]
        # inbound to interior
        if gi.in_lid:
            oxy=linkxy(net,gi.in_lid); cnt=ei_in[i]*SAMPLE
            k=int(cnt)+ (1 if RNG.random()<(cnt-int(cnt)) else 0)
            for _ in range(max(k,0)):
                d=pool[RNG.integers(len(pool))]
                trips.append((gi.in_lid,oxy[0],oxy[1],None,d[0],d[1],gi.truck_frac))
        # interior to gateway (outbound)
        if gi.out_lid:
            dxy=linkxy(net,gi.out_lid); cnt=ei_out[i]*SAMPLE
            k=int(cnt)+ (1 if RNG.random()<(cnt-int(cnt)) else 0)
            for _ in range(max(k,0)):
                o=pool[RNG.integers(len(pool))]
                trips.append((None,o[0],o[1],gi.out_lid,dxy[0],dxy[1],gi.truck_frac))
    ncordon=len(trips)
    print(f"  cordon (through + E-I) agents: {ncordon:,}")
    # --- internal freeway uplift (ODME): clone a calibrated fraction of long resident car trips ---
    if clone_frac>0:
        long_od=load_long_car_trips()   # 10% sample coords
        nclone=int(round(len(long_od)*clone_frac))
        idx=RNG.integers(0, len(long_od), size=nclone)
        for o in long_od[idx]:
            is_frwy_truck=0.05   # ~5% of long internal clones tagged truck (internal freight)
            trips.append((None,o[0],o[1],None,o[2],o[3],is_frwy_truck))
        print(f"  internal uplift clones: {nclone:,} (clone_frac={clone_frac:.2f} of {len(long_od):,} long car trips)")
    ntr=len(trips)
    deps=sample_departures(ntr, prof)
    truck_draw=RNG.random(ntr)
    print(f"generated {ntr:,} background agents (10% sample -> ~{ntr*10:,} veh/day)")
    ntruck=0
    with gzip.open(OUT_CORDON,"wt") as w:
        w.write('<?xml version="1.0" encoding="utf-8"?>\n')
        w.write('<!DOCTYPE population SYSTEM "http://www.matsim.org/files/dtd/population_v6.dtd">\n')
        w.write('<population>\n')
        for idx,(ol,ox,oy,dl,dx,dy,tp) in enumerate(trips):
            is_truck = truck_draw[idx] < tp
            ntruck += is_truck
            emit_agent(w, f"bg_{idx}", ol,ox,oy, dl,dx,dy, int(deps[idx]), is_truck)
        w.write('</population>\n')
    print(f"  trucks tagged: {ntruck:,} ({100*ntruck/max(ntr,1):.1f}%)")
    print(f"wrote {OUT_CORDON}")
    # combined = base plans + background
    print("assembling combined plans...")
    with gzip.open(OUT_COMBINED,"wt") as w:
        with gzip.open(BASE_POP,"rt") as f:
            for line in f:
                if "</population>" in line: continue
                w.write(line)
        with gzip.open(OUT_CORDON,"rt") as f:
            skip=True
            for line in f:
                if "<population>" in line: skip=False; continue
                if skip: continue
                if "</population>" in line: continue
                w.write(line)
        w.write('</population>\n')
    print(f"wrote {OUT_COMBINED}")

# --------------------------------------------------------------------- entry
def main():
    mode = sys.argv[1] if len(sys.argv)>1 else "diagnose"
    CALIB.mkdir(parents=True, exist_ok=True)
    print("parsing network + linkstats...")
    net=build_network()
    gwc=build_gateways(net)
    gwc=attach_cordon_aadt(gwc)
    gwc=add_known_missed_gateways(gwc)
    gwc["cur_vol"]=[current_gateway_vol(g, net["ls"]) for _,g in gwc.iterrows()]
    gwc["external"]=(gwc.cordon_aadt-gwc.cur_vol).clip(lower=0.0)
    gwc.to_csv(CALIB/"gateways_2023.csv", index=False)
    pd.set_option("display.width",240,"display.max_columns",30)
    show=gwc[["cx","cy","hwy","road","prefix","cordon_aadt","cur_vol","external","truck_frac","snap_d"]].sort_values("cordon_aadt",ascending=False)
    print(f"\nphysical gateways: {len(gwc)}")
    print(show.to_string(index=False, formatters={c:"{:.0f}".format for c in ["cx","cy","cordon_aadt","cur_vol","external","snap_d"]}|{"truck_frac":"{:.3f}".format}))
    print(f"\ntotal external both-dir daily: {gwc.external.sum():,.0f}")

    print("\nfree-flow pre-assignment (EE + EI unit matrices)...")
    ee_vol, ei_vol = unit_matrices(gwc, net)
    scr, best = calibrate_through_frac(gwc, net, ee_vol, ei_vol)
    score,phi,ratio,medgeh = best
    print(f"interior IS screenlines: n={len(scr)}  base ratio={scr.model_daily.sum()/scr.obs_AADT.sum():.2f}")
    print(f"CALIBRATED THROUGH_FRAC phi={phi:.2f} -> interior model/obs ratio={ratio:.2f}, median GEH={medgeh:.1f}")
    # report the phi sweep
    def link_sum(lv, ids): return sum(lv.get(l,0.0) for l in ids.split(";"))
    ee=np.array([link_sum(ee_vol,ids) for ids in scr.link_ids])
    ei=np.array([link_sum(ei_vol,ids) for ids in scr.link_ids])
    PHI=0.70   # keep a majority-through split (favours interior corridor loading) with some E-I
    thru = scr.model_daily.values + PHI*ee + (1-PHI)*ei     # interior after cordon-through only

    # --- internal freeway uplift calibration: clone long resident car trips to close the residual ---
    print("\nsampled free-flow pre-assignment of long internal car trips (for uplift calibration)...")
    want_links=set()
    for ids in scr.link_ids: want_links.update(ids.split(";"))
    long_od=load_long_car_trips()
    Ntot_full=len(long_od)*10.0
    samp = long_od if len(long_od)<=15000 else long_od[RNG.choice(len(long_od),15000,replace=False)]
    lv_int, used = preassign_internal(samp, net, want_links, nsrc_cap=800)
    per_full = Ntot_full/max(used,1)
    int_contrib=np.array([sum(lv_int.get(l,0.0)*per_full for l in ids.split(";")) for ids in scr.link_ids])
    obs=scr.obs_AADT.values
    # solve clone_frac so aggregate interior ratio hits target
    TARGET=0.90
    denom=int_contrib.sum()
    clone_frac = max(0.0,(TARGET*obs.sum()-thru.sum())/denom) if denom>0 else 0.0
    print(f"internal long car trips (full x10): {Ntot_full:,.0f}   sampled paths used: {used}")
    print(f"interior after cordon-through (phi={PHI}): ratio={thru.sum()/obs.sum():.2f}")
    for f in [0.0,0.25,0.5,0.75,1.0,1.25,1.5, round(clone_frac,2)]:
        m=thru+f*int_contrib
        print(f"  clone_frac={f:.2f}: interior ratio={m.sum()/obs.sum():.2f}  medGEH={np.nanmedian(N.geh(m,obs)):.1f}  %GEH<5={100*np.mean(N.geh(m,obs)<5):.0f}")
    print(f"==> RECOMMENDED clone_frac={clone_frac:.2f} for interior ratio {TARGET}")

    if mode=="write":
        through_frac=float(sys.argv[2]) if len(sys.argv)>2 else PHI
        scale=1.0
        cf=float(sys.argv[3]) if len(sys.argv)>3 else round(clone_frac,2)
        print(f"\n=== WRITE mode: THROUGH_FRAC={through_frac}, SCALE={scale}, CLONE_FRAC={cf} ===")
        write_plans(gwc, net, through_frac, scale, cf)

if __name__=="__main__":
    main()
