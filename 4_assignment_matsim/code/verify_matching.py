#!/usr/bin/env python3
"""QA of the AADT-station -> MATSim-link matching, so you can SEE it is correct.

Outputs into validation/gis/match_qa.gpkg (open in QGIS over an OSM basemap):
  - stations        : the AADT points (prefix, route, AADT, matched hierarchy, snap distance)
  - matched_links   : the links each station was matched to (the ones whose volume is compared)
  - connectors      : a short line from each station to its matched link  -> visually shows the snap

Plus: a statistical QA summary (snap-distance distribution, route-prefix -> matched-hierarchy
consistency) and zoomed proof maps for sample stations of each road type.
"""
from pathlib import Path
import pandas as pd, geopandas as gpd, numpy as np
from shapely.geometry import LineString
from shapely.ops import nearest_points
import sys; sys.path.insert(0,str(Path(__file__).parent))
from validate_matsim_counts import link_gdf

ROOT=Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
AADT=ROOT/"data/aadt_2017_bmr.geojson"
QA=ROOT/"validation/gis/match_qa.gpkg"

def main():
    g=link_gdf(); gid=dict(zip(g.id,g.geometry))
    m=pd.read_csv(ROOT/"validation/station_link_map.csv")
    m["links"]=m.link_ids.map(lambda s:str(s).split(";") if pd.notna(s) else [])
    pts=gpd.read_file(AADT).to_crs("EPSG:26985").set_index("LOCATION_ID")
    conn=[]; mlinks=set()
    for _,r in m.iterrows():
        if r.LOCATION_ID not in pts.index or not r.links: continue
        p=pts.loc[r.LOCATION_ID].geometry
        prim=r.links[0]; mlinks.update(r.links)
        if prim in gid:
            np_pt=nearest_points(p, gid[prim])[1]
            conn.append({"LOCATION_ID":r.LOCATION_ID,"ID_PREFIX":r.ID_PREFIX,"ID_RTE_NO":r.ID_RTE_NO,
                         "AADT_2017":r.AADT_2017,"hwy":r.hwy,"snap_m":round(r.min_dist,1),
                         "n_links":r.n_links,"geometry":LineString([p,np_pt])})
    gpd.GeoDataFrame(conn,crs="EPSG:26985").to_file(QA,layer="connectors",driver="GPKG")
    # stations layer (points) with match attributes
    sta=pts.loc[[c["LOCATION_ID"] for c in conn]].reset_index()[["LOCATION_ID","geometry"]]
    sta=sta.merge(pd.DataFrame(conn).drop(columns="geometry"),on="LOCATION_ID")
    gpd.GeoDataFrame(sta,crs="EPSG:26985").to_file(QA,layer="stations",driver="GPKG")
    g[g.id.isin(mlinks)][["id","hwy","cap","geometry"]].to_file(QA,layer="matched_links",driver="GPKG")
    print(f"wrote {QA}  (layers: stations, matched_links, connectors)")

    # --- statistical QA ---
    d=pd.DataFrame(conn)
    print("\n=== snap-distance distribution (station -> matched link), metres ===")
    print(f"  median {d.snap_m.median():.1f} | 75th {d.snap_m.quantile(.75):.1f} | 90th {d.snap_m.quantile(.9):.1f} | max {d.snap_m.max():.1f}")
    print(f"  within 10 m: {100*(d.snap_m<=10).mean():.0f}%   within 25 m: {100*(d.snap_m<=25).mean():.0f}%")
    print("\n=== route prefix -> matched OSM hierarchy (consistency check) ===")
    d["mainhwy"]=d.hwy.str.split(";").str[0]
    ct=pd.crosstab(d.ID_PREFIX, d.mainhwy)
    print(ct.to_string())

    # --- zoomed proof maps for one sample station per road type ---
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    samples={"IS":695,"US":None,"MD":None,"CO":None}
    fig,axes=plt.subplots(1,4,figsize=(22,6))
    for ax,(pref,rte) in zip(axes,samples.items()):
        cand=d[(d.ID_PREFIX==pref)] if rte is None else d[(d.ID_PREFIX==pref)&(d.ID_RTE_NO==rte)]
        if len(cand)==0: ax.set_axis_off(); continue
        row=cand.iloc[len(cand)//2]; sid=row.LOCATION_ID
        p=pts.loc[sid].geometry; pad=400
        ext=[p.x-pad,p.x+pad,p.y-pad,p.y+pad]
        sub=g.cx[ext[0]:ext[1],ext[2]:ext[3]]
        sub.plot(ax=ax,color="#cccccc",lw=0.6)
        ml=g[g.id.isin(m[m.LOCATION_ID==sid].links.iloc[0])]
        ml.plot(ax=ax,color="#1f77b4",lw=2.5)
        ax.scatter([p.x],[p.y],c="red",s=60,zorder=5,marker="*")
        ax.set_xlim(ext[0],ext[1]); ax.set_ylim(ext[2],ext[3]); ax.set_aspect("equal"); ax.set_axis_off()
        ax.set_title(f"{pref}-{int(row.ID_RTE_NO)} station {sid}\nAADT {int(row.AADT_2017):,}, snap {row.snap_m:.0f} m, matched {row.hwy}",fontsize=9)
    plt.suptitle("Match QA — red star = AADT station; blue = matched MATSim link(s); grey = network",fontsize=12)
    plt.tight_layout(); plt.savefig(ROOT/"validation/figures/match_qa_zoom.png",dpi=150,bbox_inches="tight"); plt.close()
    print("\nwrote validation/figures/match_qa_zoom.png")

if __name__=="__main__":
    main()
