#!/usr/bin/env python3
"""MATSim link-volume validation vs MDOT SHA AADT (2017) + FHWA TMAS hourly (2017), for the BMR.

Two stages:
  match    — parse the MATSim car network, snap each AADT station (point) to the best nearby car link
             (highest road hierarchy within tolerance, then nearest), pairing the opposing-direction link
             too. Writes validation/station_link_map.csv + a match-quality map. (run before/independent of MATSim.)
  validate — parse a MATSim events file for per-link hourly volumes, scale by 1/sample, sum both directions
             at each station, compare to AADT (daily) and TMAS (hourly): GEH, %RMSE, scatter + GIS overlay.

Usage:
  python validate_matsim_counts.py match
  python validate_matsim_counts.py validate <events.xml.gz> <sampleScale>   # sampleScale=20 for 5%
"""
import sys, gzip, re, math, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
NET  = ROOT/"input/network/bmr_network_pt_simplified.xml.gz"
# AADT count year: 2023 = base/validation year (latest published MDOT SHA AADT, ACS-validated SILO).
# The AADT_2017 field in the geojson carries the chosen-year value (schema kept stable). Override via AADT_FILE.
AADT = Path(os.environ.get("AADT_FILE", str(ROOT/"data/aadt_2023_bmr.geojson")))
OUTM = ROOT/"validation/station_link_map.csv"
HWY_RANK = {"motorway":6,"trunk":5,"primary":4,"secondary":3,"tertiary":2,
            "motorway_link":3,"trunk_link":3,"primary_link":2,"secondary_link":2,"tertiary_link":1}

# ---------------------------------------------------------------- network parsing
def parse_network():
    nodes={}; links=[]
    nre=re.compile(r'<node id="([^"]+)" x="([^"]+)" y="([^"]+)"')
    lstart=re.compile(r'<link id="([^"]+)" from="([^"]+)" to="([^"]+)".*?modes="([^"]+)"')
    caps=re.compile(r'capacity="([^"]+)"'); hw=re.compile(r'osm:way:highway" class="java.lang.String">([^<]+)<')
    cur=None
    with gzip.open(NET,"rt") as f:
        for line in f:
            m=nre.search(line)
            if m: nodes[m.group(1)]=(float(m.group(2)),float(m.group(3))); continue
            m=lstart.search(line)
            if m:
                if "car" in m.group(4).split(","):
                    cm=caps.search(line)
                    cur={"id":m.group(1),"from":m.group(2),"to":m.group(3),
                         "cap":float(cm.group(1)) if cm else 0.0,"hwy":""}
                else: cur=None
                continue
            if cur is not None:
                hm=hw.search(line)
                if hm: cur["hwy"]=hm.group(1)
                if "</link>" in line:
                    links.append(cur); cur=None
    return nodes, links

def link_gdf():
    import geopandas as gpd
    from shapely.geometry import LineString, Point
    nodes, links = parse_network()
    rows=[]
    for l in links:
        if l["from"] not in nodes or l["to"] not in nodes: continue
        a=nodes[l["from"]]; b=nodes[l["to"]]
        rows.append({**l, "fx":a[0],"fy":a[1],"tx":b[0],"ty":b[1],
                     "rank":HWY_RANK.get(l["hwy"],0),"geometry":LineString([a,b])})
    g=gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:26985")
    # unit direction vector per link (for parallel/anti-parallel carriageway detection)
    import numpy as _np
    dx=g.tx-g.fx; dy=g.ty-g.fy; ln=_np.hypot(dx,dy).replace(0,1)
    g["ux"]=dx/ln; g["uy"]=dy/ln
    return g

# AADT route prefix -> permissible OSM highway classes (so an interstate count matches the freeway
# mainline, not a parallel surface street, and a county-road count doesn't grab an overpassing freeway).
PREFIX_HWY = {
    "IS": {"motorway"},
    "US": {"motorway","trunk","primary","motorway_link","trunk_link"},
    "MD": {"trunk","primary","secondary","tertiary","trunk_link","primary_link","secondary_link"},
    "CO": {"secondary","tertiary","primary","tertiary_link","secondary_link"},
    "MU": {"tertiary","secondary","residential","tertiary_link"},
    "RP": {"motorway_link","trunk_link","primary_link","secondary_link","tertiary_link"},  # ramp counts
}
PREFIX_TOL = {"IS":70.0,"US":60.0,"RP":40.0}   # freeways are wide / divided -> larger search radius

# ---------------------------------------------------------------- stage: match
def do_match():
    import geopandas as gpd
    g=link_gdf()
    print(f"car links: {len(g):,}")
    aadt=gpd.read_file(AADT).to_crs("EPSG:26985")
    aadt=aadt[aadt.AADT_2017>0].copy()
    grec=g[["id","hwy","ux","uy"]].copy()
    gid=dict(zip(g.id, g.geometry)); ghwy=dict(zip(g.id,g.hwy))
    gux=dict(zip(g.id,g.ux)); guy=dict(zip(g.id,g.uy)); gidx=dict(zip(range(len(g)),g.id))
    sidx=g.sindex
    rows=[]
    for _,s in aadt.iterrows():
        pref=s.ID_PREFIX; tol=PREFIX_TOL.get(pref,45.0); allowed=PREFIX_HWY.get(pref,None)
        cand=list(sidx.query(s.geometry.buffer(tol), predicate="intersects"))
        # in-class candidate links with distance
        cl=[]
        for idx in cand:
            lid=gidx[idx]; hw=ghwy[lid]
            if allowed is not None and hw not in allowed: continue
            d=s.geometry.distance(gid[lid])
            if d<=tol: cl.append((lid,hw,d))
        if not cl:  # fallback: single nearest car link <45 m, any class
            best=None
            for idx in cand:
                lid=gidx[idx]; d=s.geometry.distance(gid[lid])
                if d<=45 and (best is None or d<best[2]): best=(lid,ghwy[lid],d)
            if best: cl=[best]
        if not cl: continue
        cl.sort(key=lambda t:t[2])
        prim=cl[0]; d0=(gux[prim[0]],guy[prim[0]])
        # opposite-direction nearest in-class link (other carriageway / reverse): dir dot < -0.5
        opp=None
        for lid,hw,d in cl[1:]:
            if gux[lid]*d0[0]+guy[lid]*d0[1] < -0.5: opp=(lid,hw,d); break
        chosen=[prim]+([opp] if opp else [])
        link_ids=";".join(l[0] for l in chosen)
        hwys=";".join(sorted(set(l[1] for l in chosen)))
        rows.append({**s.drop("geometry").to_dict(), "link_ids":link_ids, "n_links":len(chosen),
                     "hwy":hwys, "min_dist":prim[2]})
    matched=pd.DataFrame(rows)
    print(f"stations matched: {len(matched):,} of {len(aadt):,} ({100*len(matched)/len(aadt):.1f}%); "
          f"avg links/station {matched.n_links.mean():.1f}")
    keep=["LOCATION_ID","COUNTY_DESC","ID_PREFIX","ID_RTE_NO","PEAK_HOUR_DIRECTION","AADT_2017","AAWDT_2017",
          "K_FACTOR","D_FACTOR","link_ids","n_links","hwy","min_dist"]
    matched[keep].to_csv(OUTM, index=False)
    print(f"wrote {OUTM}")
    # quick match-quality map
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,10))
    g.sample(min(40000,len(g))).plot(ax=ax,color="#DDDDDD",lw=0.2,zorder=1)
    m=matched.copy(); m["geometry"]=m.geometry
    gpd.GeoDataFrame(m,geometry="geometry",crs="EPSG:26985").plot(ax=ax,column="dist",cmap="viridis",
        markersize=4,legend=True,zorder=3,legend_kwds={"label":"snap distance (m)","shrink":0.5})
    ax.set_title(f"AADT 2017 stations snapped to MATSim car links — {len(matched):,} matched (<{TOL:.0f} m)")
    ax.set_xlabel("Easting (EPSG:26985)"); ax.set_ylabel("Northing")
    plt.tight_layout(); plt.savefig(ROOT/"validation/figures/aadt_link_match.png",dpi=140,bbox_inches="tight"); plt.close()
    print("wrote validation/figures/aadt_link_match.png")

# ---------------------------------------------------------------- stage: validate (after a run)
def _sid(x):  # normalize a link id to the string form MATSim events use ("45952"), or None
    return None if pd.isna(x) else str(int(float(x)))

def do_validate(events_path, scale):
    mapping=pd.read_csv(OUTM)
    mapping["links"]=mapping.link_ids.map(lambda s: str(s).split(";") if pd.notna(s) else [])
    want=set(l for ls in mapping.links for l in ls)
    # parse events for link entries (vehicle enters link) per link per hour
    vol=np.zeros((0,))  # placeholder
    import collections
    hourly=collections.defaultdict(lambda: np.zeros(24))
    daily=collections.defaultdict(float)
    ev=re.compile(r'time="([0-9.]+)".*?type="(entered link|left link)".*?link="([^"]+)"')
    enter=re.compile(r'type="entered link"'); linkre=re.compile(r'link="([^"]+)"'); timere=re.compile(r'time="([0-9.]+)"')
    opn=gzip.open if str(events_path).endswith(".gz") else open
    with opn(events_path,"rt") as f:
        for line in f:
            if "entered link" not in line: continue
            lm=linkre.search(line); tm=timere.search(line)
            if not lm or not tm: continue
            lid=lm.group(1)
            if lid not in want: continue
            h=int(float(tm.group(1))//3600) % 24
            hourly[lid][h]+=scale; daily[lid]+=scale
    rows=[]
    for _,r in mapping.iterrows():
        model=sum(daily.get(l,0.0) for l in r.links)   # sum all in-class carriageways at the station
        obs=r.AADT_2017
        geh=math.sqrt(2*(model-obs)**2/(model+obs)) if (model+obs)>0 else np.nan
        rows.append({"LOCATION_ID":r.LOCATION_ID,"ID_PREFIX":r.ID_PREFIX,"ID_RTE_NO":r.ID_RTE_NO,"hwy":r.hwy,
                     "obs_AADT":obs,"model_daily":model,"diff":model-obs,
                     "pct":100*(model-obs)/obs if obs>0 else np.nan,"GEH":geh})
    res=pd.DataFrame(rows)
    res.to_csv(ROOT/"validation/aadt_validation.csv", index=False)
    ok=res.dropna(subset=["GEH"])
    print(f"validated stations: {len(ok):,}")
    print(f"GEH<5 : {100*(ok.GEH<5).mean():.1f}%   GEH<10: {100*(ok.GEH<10).mean():.1f}%   median GEH {ok.GEH.median():.2f}")
    print(f"%RMSE : {math.sqrt((ok.pct**2).mean()):.1f}%   mean bias {ok.pct.mean():+.1f}%")
    # scatter
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,7))
    c=["#2E8B57" if x<5 else "#E69500" if x<10 else "#C0392B" for x in ok.GEH]
    ax.scatter(ok.obs_AADT, ok.model_daily, s=8, c=c, alpha=0.5)
    mx=max(ok.obs_AADT.max(), ok.model_daily.max())
    ax.plot([0,mx],[0,mx],"k--",lw=1)
    ax.set_xlabel("Observed AADT 2017"); ax.set_ylabel("MATSim daily volume (both dir, scaled)")
    ax.set_title(f"MATSim vs AADT — GEH<5: {100*(ok.GEH<5).mean():.0f}%, %RMSE {math.sqrt((ok.pct**2).mean()):.0f}%")
    ax.set_xscale("log"); ax.set_yscale("log")
    plt.tight_layout(); plt.savefig(ROOT/"validation/figures/aadt_scatter.png",dpi=140,bbox_inches="tight"); plt.close()
    print("wrote validation/aadt_validation.csv + figures/aadt_scatter.png")

# ---------------------------------------------------------------- GIS outputs (QGIS/ArcGIS + interactive)
def do_gis():
    """Build GIS deliverables from the station↔link map (+ validation results if present):
       - GeoPackage (stations + matched links) for QGIS/ArcGIS
       - interactive folium map on an OSM basemap (GEH if available, else observed AADT)
       - static GEH choropleth + spatial-bias maps."""
    import geopandas as gpd, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    m=pd.read_csv(OUTM)
    m["links"]=m.link_ids.map(lambda s: str(s).split(";") if pd.notna(s) else [])
    allmatched=set(l for ls in m.links for l in ls)
    aadt=gpd.read_file(AADT).to_crs("EPSG:26985")[["LOCATION_ID","geometry"]]
    st=aadt.merge(m, on="LOCATION_ID", how="inner")
    # join validation results if the run has been validated
    valf=ROOT/"validation/aadt_validation.csv"
    has_val=valf.exists()
    if has_val:
        st=st.merge(pd.read_csv(valf)[["LOCATION_ID","model_daily","diff","pct","GEH"]], on="LOCATION_ID", how="left")
    g=link_gdf()
    matched_links=g[g.id.isin(allmatched)].copy()
    if has_val:
        vol=pd.read_csv(valf).set_index("LOCATION_ID")
        l2v={}
        for _,r in m.iterrows():
            if r.LOCATION_ID in vol.index:
                for l in r.links: l2v[l]=vol.loc[r.LOCATION_ID,"model_daily"]
        matched_links["model_daily"]=matched_links.id.map(l2v)
    # --- GeoPackage (QGIS/ArcGIS) --- drop python-object/list columns GIS tools can't render
    gpkg=ROOT/"validation/gis/baltimore_validation.gpkg"
    if gpkg.exists(): gpkg.unlink()
    def gis_clean(gdf):
        drop=[c for c in gdf.columns if c!="geometry" and gdf[c].map(lambda v: isinstance(v,(list,dict))).any()]
        return gdf.drop(columns=drop)
    gis_clean(st).to_file(gpkg, layer="aadt_stations", driver="GPKG")
    gis_clean(matched_links.drop(columns=["fx","fy","tx","ty"])).to_file(gpkg, layer="matched_links", driver="GPKG")
    print(f"wrote {gpkg} (layers: aadt_stations, matched_links)")
    # --- interactive folium map on OSM basemap ---
    import folium, branca.colormap as cm
    st_wgs=st.to_crs("EPSG:4326")
    col = "GEH" if has_val else "AADT_2017"
    center=[st_wgs.geometry.y.mean(), st_wgs.geometry.x.mean()]
    fmap=folium.Map(location=center, zoom_start=10, tiles="CartoDB positron")
    if has_val:
        def color(v): return "#2E8B57" if v<5 else "#E69500" if v<10 else "#C0392B"
        for _,r in st_wgs.iterrows():
            if pd.isna(r.get("GEH")): continue
            folium.CircleMarker([r.geometry.y,r.geometry.x], radius=3, color=color(r.GEH), fill=True,
                fill_opacity=0.7, popup=f"{r.LOCATION_ID} {r.ID_PREFIX}{int(r.ID_RTE_NO)}<br>obs {int(r.AADT_2017):,} / model {int(r.model_daily):,}<br>GEH {r.GEH:.1f} ({r.pct:+.0f}%)").add_to(fmap)
        folium.map.Marker([center[0],center[1]]).add_to(fmap)
    else:
        cmap=cm.linear.viridis.scale(st_wgs.AADT_2017.min(), st_wgs.AADT_2017.quantile(0.95))
        for _,r in st_wgs.iterrows():
            folium.CircleMarker([r.geometry.y,r.geometry.x], radius=3, color=cmap(min(r.AADT_2017,st_wgs.AADT_2017.quantile(0.95))),
                fill=True, fill_opacity=0.7, popup=f"{r.LOCATION_ID} {r.ID_PREFIX}{int(r.ID_RTE_NO)}<br>AADT2017 {int(r.AADT_2017):,}").add_to(fmap)
        cmap.add_to(fmap)
    out_html=ROOT/"validation/gis/validation_map.html"
    fmap.save(str(out_html)); print(f"wrote {out_html} (interactive, OSM basemap)")
    # --- static maps ---
    if has_val:
        sv=st[st.GEH.notna()].copy()
        fig,axes=plt.subplots(1,2,figsize=(20,10))
        g.sample(min(30000,len(g))).plot(ax=axes[0],color="#E5E5E5",lw=0.2)
        cats=pd.cut(sv.GEH,[0,5,10,1e9],labels=["GEH<5 (good)","5–10 (fair)","≥10 (poor)"])
        for c,col in zip(["GEH<5 (good)","5–10 (fair)","≥10 (poor)"],["#2E8B57","#E69500","#C0392B"]):
            sub=sv[cats==c]; sub.plot(ax=axes[0],color=col,markersize=6,label=f"{c}: {len(sub)}")
        axes[0].legend(); axes[0].set_title("GEH by station"); axes[0].set_axis_off()
        g.sample(min(30000,len(g))).plot(ax=axes[1],color="#E5E5E5",lw=0.2)
        sv.plot(ax=axes[1],column="pct",cmap="RdBu_r",vmin=-60,vmax=60,markersize=6,legend=True,
                legend_kwds={"label":"% diff (model−obs)","shrink":0.5})
        axes[1].set_title("Spatial bias (over/under-prediction)"); axes[1].set_axis_off()
        plt.tight_layout(); plt.savefig(ROOT/"validation/figures/gis_geh_bias.png",dpi=140,bbox_inches="tight"); plt.close()
        print("wrote validation/figures/gis_geh_bias.png")

def parse_link_volumes(events_path, scale):
    """daily per-link entered-link volume (already scaled by 1/sample)."""
    import collections
    daily=collections.defaultdict(float)
    linkre=re.compile(r'link="([^"]+)"')
    opn=gzip.open if str(events_path).endswith(".gz") else open
    with opn(events_path,"rt") as f:
        for line in f:
            if "entered link" not in line: continue
            m=linkre.search(line)
            if m: daily[m.group(1)]+=scale
    return daily

def do_validate_loaded(events_path, scale):
    """Volume-aware station->link matching: snap each AADT station to the LOADED in-class carriageway(s)
    actually used by routed vehicles (the old geometry-only match landed 2/3 of stations on unloaded
    ramp/stub fragments). Per station: among in-class car links within tolerance that carry volume, the
    primary carriageway = highest-volume link; the model count = primary + the highest-volume opposing
    carriageway (anti-parallel) -> both directions, once each. Reports honestly; the resident-only demand
    carries no trucks / through / external-internal traffic, so a negative freeway bias is EXPECTED."""
    import geopandas as gpd, numpy as np
    g=link_gdf(); print(f"car links: {len(g):,}")
    vol=parse_link_volumes(events_path, scale)
    g["vol"]=g.id.map(lambda i: vol.get(str(i),0.0))
    aadt=gpd.read_file(AADT).to_crs("EPSG:26985"); aadt=aadt[aadt.AADT_2017>0].copy()
    gid=dict(zip(g.id,g.geometry)); ghwy=dict(zip(g.id,g.hwy))
    gux=dict(zip(g.id,g.ux)); guy=dict(zip(g.id,g.uy)); gvol=dict(zip(g.id,g.vol)); gidx=dict(zip(range(len(g)),g.id))
    sidx=g.sindex; rows=[]
    for _,s in aadt.iterrows():
        pref=s.ID_PREFIX; tol=PREFIX_TOL.get(pref,45.0); allowed=PREFIX_HWY.get(pref,None)
        cand=list(sidx.query(s.geometry.buffer(tol), predicate="intersects"))
        cl=[]
        for idx in cand:
            lid=gidx[idx]; hw=ghwy[lid]
            if allowed is not None and hw not in allowed: continue
            d=s.geometry.distance(gid[lid])
            if d<=tol: cl.append(lid)
        if not cl:  # any-class fallback within 45 m
            cl=[gidx[idx] for idx in cand if s.geometry.distance(gid[gidx[idx]])<=45]
        loaded=[lid for lid in cl if gvol[lid]>0]
        if not loaded:
            model=0.0; lids=";".join(cl[:2]); nlk=0
        else:
            prim=max(loaded, key=lambda l:gvol[l]); ux,uy=gux[prim],guy[prim]
            opp=[l for l in loaded if l!=prim and gux[l]*ux+guy[l]*uy<-0.3]
            model=gvol[prim]+(max((gvol[l] for l in opp),default=0.0))
            chosen=[prim]+([max(opp,key=lambda l:gvol[l])] if opp else []); lids=";".join(chosen); nlk=len(chosen)
        obs=s.AADT_2017
        geh=math.sqrt(2*(model-obs)**2/(model+obs)) if (model+obs)>0 else np.nan
        rows.append({"LOCATION_ID":s.LOCATION_ID,"COUNTY_DESC":s.COUNTY_DESC,"ID_PREFIX":s.ID_PREFIX,
                     "ID_RTE_NO":s.ID_RTE_NO,"hwy":";".join(sorted(set(ghwy[l] for l in (lids.split(";") if lids else [])))),
                     "link_ids":lids,"n_links":nlk,"obs_AADT":obs,"model_daily":model,"diff":model-obs,
                     "pct":100*(model-obs)/obs if obs>0 else np.nan,
                     "GEH":geh,"loaded":int(model>0)})
    res=pd.DataFrame(rows); res.to_csv(ROOT/"validation/aadt_validation.csv", index=False)
    ok=res[res.model_daily>0]
    MAJ={"motorway","trunk","primary","motorway_link"}
    maj=ok[ok.hwy.apply(lambda h: any(x in MAJ for x in str(h).split(";")))]
    print(f"stations: {len(res):,}   matched to a LOADED link: {len(ok):,} ({100*len(ok)/len(res):.0f}%)")
    print(f"[loaded] GEH<5 {100*(ok.GEH<5).mean():.0f}%  GEH<10 {100*(ok.GEH<10).mean():.0f}%  median GEH {ok.GEH.median():.1f}  median bias {ok.pct.median():+.0f}%")
    print(f"[loaded major roads n={len(maj)}] GEH<10 {100*(maj.GEH<10).mean():.0f}%  median GEH {maj.GEH.median():.1f}  median bias {maj.pct.median():+.0f}%")
    print("(negative bias expected: resident-only demand omits trucks + through/external traffic)")
    return res

if __name__=="__main__":
    stage=sys.argv[1] if len(sys.argv)>1 else "match"
    if stage=="match": do_match()
    elif stage=="validate":
        do_validate_loaded(sys.argv[2], float(sys.argv[3])); do_gis()
    elif stage=="validate_old":
        do_validate(sys.argv[2], float(sys.argv[3])); do_gis()
    elif stage=="gis": do_gis()
