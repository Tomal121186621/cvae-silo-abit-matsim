#!/usr/bin/env python3
"""Robust AADT-station -> MATSim-link matching + manual-check tooling (base_speedfix run).

Improves on clean_match_aadt_2023.py with:
  * facility-gated snap tolerance (kept: freeway 80 / principal 55 / minor 30 / collector 25 m)
  * DIRECTION awareness: an AADT count is bidirectional, a MATSim link is one direction.
    Match to BOTH carriageways (nearest link + its most anti-parallel neighbour, dot<-0.7)
    and SUM their sim volume. Flag `direction_ok=False` when only one carriageway is found.
  * ROUTE/NAME consistency: prefer links whose osm:way:name matches the station ROADNAME /
    route (ID_PREFIX+ID_RTE_NO); a freeway count is not allowed to fall onto a parallel
    arterial and vice-versa (capacity + class + name gate).
  * REJECT ramp/connector links (osm '*_link') when the station is a mainline count.
  * a per-station match_quality flag {good, single_dir, weak_snap, name_mismatch, no_match}.

Volumes come from base_speedfix it.64 linkstats (10% sample -> x10).

Outputs (network_validation_2023/manual_check/):
  station_link_match_audit.csv   full per-station audit, sorted bad-first
  bad_matches.csv                match_quality!=good OR GEH>10
  station_link_check.html        self-contained Folium click-through map
and refreshes network_validation_2023/qgis/{aadt_stations,matched_links,
station_link_connectors}.shp (EPSG:26985) with the corrected geometry + volumes.
"""
import gzip, re, os
from pathlib import Path
import numpy as np, pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points
from pyproj import Transformer

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
RUN  = ROOT/"scenarios/02_i695_congestion_pricing/output_base/base_speedfix"
NET  = RUN/"output_network.xml.gz"
LINKSTATS = RUN/"ITERS/it.64/64.linkstats.txt.gz"
AADT_CSV  = ROOT/"network_validation_2023/transitfix/aadt/aadt_validation_2023_cleaned.csv"
GEOJSON   = ROOT/"data/aadt_2023_bmr_REAL.geojson"
OUTDIR    = ROOT/"network_validation_2023/manual_check"
QGISDIR   = ROOT/"network_validation_2023/qgis"
CRS = "EPSG:26985"
SAMPLE_SCALE = 10.0
OUTDIR.mkdir(parents=True, exist_ok=True)

FSYS_GROUP = {1:"Interstate/Freeway",2:"Interstate/Freeway",3:"Principal Arterial",
              4:"Minor Arterial",5:"Collector/Local",6:"Collector/Local",7:"Collector/Local"}
# same-class OSM highway gate (an interstate count matches the freeway mainline, not a
# parallel surface street, and vice-versa)
FSYS_HWY = {
    1:{"motorway","motorway_link","trunk"},
    2:{"motorway","trunk","motorway_link","trunk_link","primary"},
    3:{"trunk","primary","secondary","trunk_link","primary_link"},
    4:{"primary","secondary","tertiary","primary_link","secondary_link"},
    5:{"secondary","tertiary","residential","unclassified","tertiary_link"},
    6:{"tertiary","residential","unclassified","secondary","living_street"},
    7:{"residential","unclassified","tertiary","living_street","service"},
}
FSYS_CAPMAX = {1:None,2:None,3:None,4:None,5:1300.0,6:1100.0,7:900.0}   # collector "bigger parallel road" ceiling
FSYS_CAPMIN = {1:1200.0,2:1000.0,3:800.0,4:None,5:None,6:None,7:None}   # mainline floor (freeway not a side street)
FSYS_TOL    = {1:80.0,2:75.0,3:55.0,4:30.0,5:25.0,6:25.0,7:25.0}
RAMP_HWY    = {"motorway_link","trunk_link","primary_link","secondary_link","tertiary_link"}


def geh(model, obs):
    model=np.asarray(model,float); obs=np.asarray(obs,float)
    with np.errstate(divide="ignore",invalid="ignore"):
        g=np.sqrt(2*(model-obs)**2/(model+obs))
    return np.where((model+obs)>0,g,np.nan)


# ------------------------------------------------------------------ name matching
_ABBR = {"st":"street","rd":"road","ave":"avenue","av":"avenue","dr":"drive",
         "blvd":"boulevard","hwy":"highway","pkwy":"parkway","pky":"parkway",
         "ln":"lane","ct":"court","pl":"place","rte":"route","cir":"circle",
         "ter":"terrace","trl":"trail","pike":"pike","sq":"square",
         "n":"north","s":"south","e":"east","w":"west",
         "ne":"northeast","nw":"northwest","se":"southeast","sw":"southwest",
         "md":"maryland","us":"us","is":"interstate","i":"interstate"}
_STOP = {"the","of","to","at","and","state","route","road","street","us","interstate"}

def toks(name):
    if not name or (isinstance(name,float) and np.isnan(name)): return set()
    s = re.sub(r"[^a-z0-9 ]"," ",str(name).lower())
    out=set()
    for w in s.split():
        out.add(_ABBR.get(w,w))
    return out

def station_tokens(roadname, prefix, rte):
    t = toks(roadname)
    if isinstance(rte,(int,float)) and not (isinstance(rte,float) and np.isnan(rte)):
        rno = str(int(rte))
        t.add(rno)
        pfx = str(prefix).lower() if isinstance(prefix,str) else ""
        if pfx in ("md",): t |= {"maryland","route", rno}
        if pfx in ("us",): t |= {"us","route", rno}
        if pfx in ("is","i"): t |= {"interstate", rno}
    return t

def name_match(st_toks, link_name):
    """True/False/None (None = link has no usable name -> cannot judge)."""
    lt = toks(link_name)
    lt_meaningful = lt - _STOP
    if not lt_meaningful: return None
    st_meaningful = st_toks - _STOP
    if not st_meaningful: return None
    return len(st_meaningful & lt_meaningful) > 0


# ------------------------------------------------------------------ network parse
def parse_network():
    nodes={}; links=[]
    nre=re.compile(r'<node id="([^"]+)" x="([^"]+)" y="([^"]+)"')
    lstart=re.compile(r'<link id="([^"]+)" from="([^"]+)" to="([^"]+)".*?freespeed="([^"]+)".*?capacity="([^"]+)".*?permlanes="([^"]+)".*?modes="([^"]+)"')
    hw=re.compile(r'osm:way:highway" class="java.lang.String">([^<]+)<')
    nm=re.compile(r'osm:way:name" class="java.lang.String">([^<]+)<')
    cur=None
    with gzip.open(NET,"rt") as f:
        for line in f:
            m=nre.search(line)
            if m: nodes[m.group(1)]=(float(m.group(2)),float(m.group(3))); continue
            m=lstart.search(line)
            if m:
                if "car" in m.group(7).split(","):
                    cur={"id":m.group(1),"from":m.group(2),"to":m.group(3),
                         "freespeed":float(m.group(4)),"cap":float(m.group(5)),
                         "permlanes":float(m.group(6)),"hwy":"","name":""}
                else: cur=None
                continue
            if cur is not None:
                hm=hw.search(line)
                if hm: cur["hwy"]=hm.group(1)
                nmm=nm.search(line)
                if nmm and not cur["name"]: cur["name"]=nmm.group(1)
                if "</link>" in line:
                    links.append(cur); cur=None
    return nodes, links

def load_vol():
    df=pd.read_csv(LINKSTATS, sep="\t", dtype={"LINK":str})
    df["vol24"]=df["HRS0-24avg"]*SAMPLE_SCALE
    return dict(zip(df["LINK"], df["vol24"]))

def link_gdf():
    nodes,links=parse_network(); vol=load_vol()
    rows=[]
    for l in links:
        if l["from"] not in nodes or l["to"] not in nodes: continue
        a=nodes[l["from"]]; b=nodes[l["to"]]
        rows.append({**l,"fx":a[0],"fy":a[1],"tx":b[0],"ty":b[1],
                     "geometry":LineString([a,b]),"vol24":vol.get(l["id"],0.0)})
    g=gpd.GeoDataFrame(rows,geometry="geometry",crs=CRS)
    dx=g.tx-g.fx; dy=g.ty-g.fy; ln=np.hypot(dx,dy).replace(0,1)
    g["ux"]=dx/ln; g["uy"]=dy/ln
    return g


# ------------------------------------------------------------------ matcher
def match(g):
    df = pd.read_csv(AADT_CSV)
    df = df[df.obs_AADT > 0].copy()
    # extra geometry / direction fields from the genuine geojson
    try:
        gj = gpd.read_file(GEOJSON)[["LOCATION_ID","PEAK_HOUR_DIRECTION","NUM_LANES","MAIN_LINE"]]
        df = df.merge(gj, on="LOCATION_ID", how="left")
    except Exception:
        df["MAIN_LINE"]=np.nan
    gid={i:lid for i,lid in enumerate(g.id)}
    G={lid:r for lid,r in zip(g.id, g.to_dict("records"))}
    geom=dict(zip(g.id,g.geometry))
    sidx=g.sindex
    rows=[]
    old_map = dict(zip(df.LOCATION_ID, df.get("link_ids", pd.Series(index=df.index,dtype=object)).fillna("")))
    for _,s in df.iterrows():
        fs=int(s.F_SYSTEM) if pd.notna(s.F_SYSTEM) else 4
        st_toks=station_tokens(s.ROADNAME, s.ID_PREFIX, s.ID_RTE_NO)
        is_ramp = (s.ID_PREFIX=="RP") or (str(s.get("facility",""))=="Ramp")
        tol=FSYS_TOL.get(fs,45.0)
        if is_ramp: tol=min(tol,45.0)
        allowed=FSYS_HWY.get(fs); capmax=FSYS_CAPMAX.get(fs); capmin=FSYS_CAPMIN.get(fs)
        pt=Point(s.lon, s.lat)
        cand=list(sidx.query(pt.buffer(tol), predicate="intersects"))
        inclass=[]
        for idx in cand:
            lid=gid[idx]; L=G[lid]
            if allowed is not None and L["hwy"] not in allowed: continue     # same-class gate
            if not is_ramp and L["hwy"] in RAMP_HWY: continue                # reject ramp links for mainline count
            d=pt.distance(geom[lid])
            if d<=tol: inclass.append((lid,d))
        # collector "bigger parallel road" ceiling: keep only under-ceiling links if any exist
        if capmax is not None and inclass:
            under=[(lid,d) for lid,d in inclass if G[lid]["cap"]<=capmax]
            if under: inclass=under
        # mainline floor: drop tiny side-street links when a real mainline link is present
        if capmin is not None and inclass:
            big=[(lid,d) for lid,d in inclass if G[lid]["cap"]>=capmin]
            if big: inclass=big
        # NAME preference: if any name-consistent link exists, drop the name-conflicting ones
        if inclass:
            named=[(lid,d,name_match(st_toks,G[lid]["name"])) for lid,d in inclass]
            if any(nm is True for _,_,nm in named):
                inclass=[(lid,d) for lid,d,nm in named if nm is not False]

        if not inclass:
            rows.append(_row(s,fs,is_ramp,[],np.nan,None,None,None,"no_match",G,geom,old_map)); continue
        inclass.sort(key=lambda t:t[1])
        prim,pd0=inclass[0]; ux,uy=G[prim]["ux"],G[prim]["uy"]
        # opposite carriageway: nearest anti-parallel in-class link
        opp=[(lid,d) for lid,d in inclass if lid!=prim and G[lid]["ux"]*ux+G[lid]["uy"]*uy<-0.7]
        opp.sort(key=lambda t:t[1])
        chosen=[prim]+([opp[0][0]] if opp else [])
        direction_ok = len(opp)>0
        # name / capacity flags on the chosen primary
        nm_prim=name_match(st_toks,G[prim]["name"])
        name_ok = nm_prim if nm_prim is not None else (
            None if not any(name_match(st_toks,G[l]["name"]) is not None for l in chosen)
            else any(name_match(st_toks,G[l]["name"]) is True for l in chosen))
        cap_prim=G[prim]["cap"]
        capacity_ok = True
        if capmax is not None and cap_prim>capmax: capacity_ok=False
        if capmin is not None and cap_prim<capmin: capacity_ok=False
        # quality
        if name_ok is False and capacity_ok is False:
            q="name_mismatch"
        elif pd0 > 0.6*tol:
            q="weak_snap"
        elif (not is_ramp) and (not direction_ok):
            q="single_dir"
        else:
            q="good"
        rows.append(_row(s,fs,is_ramp,chosen,pd0,direction_ok,name_ok,capacity_ok,q,G,geom,old_map))
    out=pd.DataFrame(rows)
    return out, len(df)

def _row(s,fs,is_ramp,chosen,snap,direction_ok,name_ok,capacity_ok,q,G,geom,old_map):
    model=sum(G[l]["vol24"] for l in chosen) if chosen else 0.0
    obs=float(s.obs_AADT)
    ratio=model/obs if obs>0 else np.nan
    gg=float(geh([model],[obs])[0]) if (model+obs)>0 else np.nan
    lid_str=";".join(chosen)
    return {"LOCATION_ID":s.LOCATION_ID,"ROADNAME":s.ROADNAME,
            "ID_PREFIX":s.get("ID_PREFIX"),"ID_RTE_NO":s.get("ID_RTE_NO"),
            "F_SYSTEM":fs,"facility":FSYS_GROUP.get(fs,"Other") if not is_ramp else "Ramp",
            "obs_AADT":obs,"matched_link_ids":lid_str,"n_links":len(chosen),
            "sim_vol":round(model,1),"ratio":round(ratio,3) if obs>0 else np.nan,
            "GEH":round(gg,2) if not np.isnan(gg) else np.nan,
            "snap_dist_m":round(float(snap),2) if not (isinstance(snap,float) and np.isnan(snap)) else np.nan,
            "direction_ok":direction_ok,"name_ok":name_ok,"capacity_ok":capacity_ok,
            "match_quality":q,"lon":s.lon,"lat":s.lat,
            "old_link_ids":old_map.get(s.LOCATION_ID,"")}


# ------------------------------------------------------------------ outputs
QRANK={"no_match":0,"name_mismatch":1,"weak_snap":2,"single_dir":3,"good":4}

def write_tables(df):
    df["_qr"]=df.match_quality.map(QRANK)
    df["_rr"]=(df.ratio-1).abs().fillna(9e9)
    df=df.sort_values(["_qr","_rr"]).drop(columns=["_qr","_rr"])
    cols=["LOCATION_ID","ROADNAME","facility","obs_AADT","matched_link_ids","n_links",
          "sim_vol","ratio","GEH","snap_dist_m","direction_ok","name_ok","capacity_ok",
          "match_quality","lon","lat","ID_PREFIX","ID_RTE_NO","old_link_ids"]
    df[cols].to_csv(OUTDIR/"station_link_match_audit.csv",index=False)
    # bad_matches = likely MATCHING problems: any non-good quality flag, or a gross
    # volume outlier (ratio>=3 / <=0.2) that usually signals a wrong-road snap rather
    # than the model's (near-universal) mild volume under-assignment. A plain GEH>10
    # cut is NOT used: on high-AADT roads GEH>10 fires even at ratio~0.95, so it would
    # flood the file with well-matched links and hide the true mis-matches.
    bad=df[(df.match_quality!="good") | (df.ratio>=3) | (df.ratio<=0.2)]
    bad[cols].to_csv(OUTDIR/"bad_matches.csv",index=False)
    return df

def ratio_color(r,q):
    if q=="no_match" or pd.isna(r): return "#888888"
    if r<0.7: return "#d7191c"       # under-assigned (red)
    if r>1.4: return "#2c7bb6"       # over-assigned (blue)
    return "#1a9641"                 # ~ok (green)

def write_map(df,g):
    import folium
    tr=Transformer.from_crs(CRS,"EPSG:4326",always_xy=True)
    def wgs(x,y):
        lon,lat=tr.transform(x,y); return (lat,lon)
    lat0,lon0=wgs(df.lon.mean(),df.lat.mean())
    m=folium.Map(location=[lat0,lon0],zoom_start=10,tiles="OpenStreetMap",prefer_canvas=True)
    fg_links=folium.FeatureGroup(name="matched links",show=True)
    fg_conn =folium.FeatureGroup(name="station->link connector",show=True)
    fg_stn  =folium.FeatureGroup(name="AADT stations",show=True)
    geom=dict(zip(g.id,g.geometry))
    for _,r in df.iterrows():
        col=ratio_color(r.ratio,r.match_quality)
        spt=Point(r.lon,r.lat); sll=wgs(r.lon,r.lat)
        chosen=[c for c in str(r.matched_link_ids).split(";") if c]
        for lid in chosen:
            gl=geom.get(lid)
            if gl is None: continue
            pts=[wgs(x,y) for x,y in gl.coords]
            folium.PolyLine(pts,color=col,weight=5,opacity=0.85,
                            popup=f"link {lid}").add_to(fg_links)
        # connector from station to nearest point on primary link
        if chosen and geom.get(chosen[0]) is not None:
            p1,p2=nearest_points(spt,geom[chosen[0]])
            folium.PolyLine([sll,wgs(p2.x,p2.y)],color="#444444",weight=1.5,
                            opacity=0.7,dash_array="4").add_to(fg_conn)
        pop=(f"<b>{r.LOCATION_ID}</b> — {r.ROADNAME}<br>"
             f"facility: {r.facility}<br>"
             f"obs_AADT: <b>{r.obs_AADT:,.0f}</b><br>"
             f"sim_vol: <b>{r.sim_vol:,.0f}</b><br>"
             f"ratio: <b>{r.ratio if pd.notna(r.ratio) else 'NA'}</b>  GEH: {r.GEH if pd.notna(r.GEH) else 'NA'}<br>"
             f"quality: <b>{r.match_quality}</b><br>"
             f"snap: {r.snap_dist_m} m  dir_ok:{r.direction_ok} name_ok:{r.name_ok} cap_ok:{r.capacity_ok}<br>"
             f"links: {r.matched_link_ids}")
        folium.CircleMarker(sll,radius=4,color="#222",weight=0.6,fill=True,
                            fill_color=col,fill_opacity=0.9,
                            popup=folium.Popup(pop,max_width=320)).add_to(fg_stn)
    fg_links.add_to(m); fg_conn.add_to(m); fg_stn.add_to(m)
    legend=('<div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:white;'
            'padding:10px 12px;border:1px solid #999;border-radius:6px;font:12px sans-serif">'
            '<b>sim/obs ratio</b><br>'
            '<span style="color:#d7191c">&#9679;</span> under (&lt;0.7)<br>'
            '<span style="color:#1a9641">&#9679;</span> ~ok (0.7–1.4)<br>'
            '<span style="color:#2c7bb6">&#9679;</span> over (&gt;1.4)<br>'
            '<span style="color:#888">&#9679;</span> no match</div>')
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(m)
    out=OUTDIR/"station_link_check.html"
    m.save(str(out))
    return out

def write_qgis(df,g):
    QGISDIR.mkdir(parents=True,exist_ok=True)
    # stations
    stn=gpd.GeoDataFrame(
        df.assign(geometry=[Point(x,y) for x,y in zip(df.lon,df.lat)])[
            ["LOCATION_ID","ROADNAME","facility","obs_AADT","sim_vol","ratio","GEH",
             "snap_dist_m","n_links","match_quality","geometry"]],
        geometry="geometry",crs=CRS).rename(columns={
            "LOCATION_ID":"loc_id","ROADNAME":"road","facility":"fac","obs_AADT":"obs_aadt",
            "snap_dist_m":"snap_m","match_quality":"match_q"})
    stn.to_file(QGISDIR/"aadt_stations.shp")
    geom=dict(zip(g.id,g.geometry))
    lrows=[]; crows=[]
    for _,r in df.iterrows():
        chosen=[c for c in str(r.matched_link_ids).split(";") if c]
        for lid in chosen:
            gl=geom.get(lid)
            if gl is None: continue
            lrows.append({"loc_id":r.LOCATION_ID,"link_id":lid,"obs_aadt":r.obs_AADT,
                          "sim_vol":r.sim_vol,"ratio":r.ratio,"match_q":r.match_quality,
                          "geometry":gl})
        if chosen and geom.get(chosen[0]) is not None:
            p1,p2=nearest_points(Point(r.lon,r.lat),geom[chosen[0]])
            crows.append({"loc_id":r.LOCATION_ID,"snap_m":r.snap_dist_m,
                          "match_q":r.match_quality,"geometry":LineString([(r.lon,r.lat),(p2.x,p2.y)])})
    gpd.GeoDataFrame(lrows,geometry="geometry",crs=CRS).to_file(QGISDIR/"matched_links.shp")
    gpd.GeoDataFrame(crows,geometry="geometry",crs=CRS).to_file(QGISDIR/"station_link_connectors.shp")


def corr2(d):
    ok=d[(d.sim_vol>0)&(d.obs_AADT>0)]
    if len(ok)<3: return np.nan,0
    c=np.corrcoef(ok.obs_AADT,ok.sim_vol)[0,1]
    return c**2,len(ok)

def main():
    print("parsing base_speedfix network + linkstats ...")
    g=link_gdf()
    print(f"  car links {len(g):,}  loaded {(g.vol24>0).sum():,}")
    df,ntot=match(g)
    df=write_tables(df)
    print(f"\nstations: {ntot}   matched: {(df.n_links>0).sum()}")
    print("\n=== match_quality distribution ===")
    print(df.match_quality.value_counts().reindex(list(QRANK)).fillna(0).astype(int).to_string())
    changed=df[df.matched_link_ids.fillna("")!=df.old_link_ids.fillna("")]
    print(f"\nmatches CHANGED vs old (clean_match) matcher: {len(changed)} / {len(df)} ({100*len(changed)/len(df):.1f}%)")
    c_all,n_all=corr2(df); c_good,n_good=corr2(df[df.match_quality=="good"])
    gm=df[df.sim_vol>0]; gm_good=df[(df.sim_vol>0)&(df.match_quality=="good")]
    print(f"\ncorr2 ALL matched   : {c_all:.3f} (n={n_all})   medianGEH {np.nanmedian(geh(gm.sim_vol,gm.obs_AADT)):.1f}")
    print(f"corr2 GOOD only     : {c_good:.3f} (n={n_good})   medianGEH {np.nanmedian(geh(gm_good.sim_vol,gm_good.obs_AADT)):.1f}")
    print(f"%GEH<5  ALL {100*np.nanmean(geh(gm.sim_vol,gm.obs_AADT)<5):.1f}   GOOD {100*np.nanmean(geh(gm_good.sim_vol,gm_good.obs_AADT)<5):.1f}")
    print("\nwriting map + qgis ...")
    hp=write_map(df,g)
    write_qgis(df,g)
    print("wrote:")
    print(" ", OUTDIR/"station_link_match_audit.csv")
    print(" ", OUTDIR/"bad_matches.csv")
    print(" ", hp)
    print(" ", QGISDIR/"aadt_stations.shp","(+ matched_links.shp, station_link_connectors.shp)")

if __name__=="__main__":
    main()
