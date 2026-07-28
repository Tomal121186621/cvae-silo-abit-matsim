#!/usr/bin/env python3
"""Export full GIS layers for QGIS: the complete MATSim road network (styled by hierarchy) and a
dedicated I-695 (Baltimore Beltway) layer, into validation/gis/baltimore_validation.gpkg.

I-695 is pulled from OpenStreetMap via the Overpass API (the MATSim links dropped the OSM `ref` tag),
then the network links lying on I-695 are tagged so they can be tolled in the pricing scenario.
"""
import json, urllib.request, urllib.parse
from pathlib import Path
import geopandas as gpd, pandas as pd
from shapely.geometry import LineString
import sys
sys.path.insert(0, str(Path(__file__).parent))
from validate_matsim_counts import link_gdf

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
GPKG = ROOT/"validation/gis/baltimore_validation.gpkg"

def fetch_i695():
    # Overpass: I-695 motorway ways with geometry, around Baltimore (POST + UA; ref may be "I 695"/"I-695")
    q = ('[out:json][timeout:120];'
         'way["ref"~"I[ -]?695"]["highway"~"motorway|trunk"](39.18,-76.95,39.52,-76.30);'
         'out geom;')
    d=None
    for ep in ("https://overpass-api.de/api/interpreter",
               "https://overpass.kumi.systems/api/interpreter",
               "https://maps.mail.ru/osm/tools/overpass/api/interpreter"):
        try:
            req=urllib.request.Request(ep, data=urllib.parse.urlencode({"data":q}).encode(),
                                       headers={"User-Agent":"baltimore-matsim/1.0"})
            d=json.load(urllib.request.urlopen(req, timeout=150)); break
        except Exception as e:
            print(f"  overpass {ep} failed: {type(e).__name__} {e}")
    if d is None: raise RuntimeError("all overpass endpoints failed")
    feats=[]
    for el in d.get("elements", []):
        if el.get("type")=="way" and el.get("geometry"):
            coords=[(p["lon"],p["lat"]) for p in el["geometry"]]
            if len(coords)>=2:
                feats.append({"osm_id":el["id"],"name":el.get("tags",{}).get("name",""),
                              "lanes":el.get("tags",{}).get("lanes",""),"geometry":LineString(coords)})
    g=gpd.GeoDataFrame(feats, geometry="geometry", crs="EPSG:4326").to_crs("EPSG:26985")
    print(f"I-695 OSM ways: {len(g)}")
    return g

def main():
    # 1. full road network
    g = link_gdf()
    g["hierarchy"] = g.hwy.str.replace("_link","",regex=False)
    net = g[["id","from","to","cap","hwy","hierarchy","geometry"]].copy()
    net.to_file(GPKG, layer="road_network", driver="GPKG")
    print(f"wrote road_network layer: {len(net):,} links")

    # 2. I-695 from OSM
    i695 = fetch_i695()
    i695.to_file(GPKG, layer="i695_osm", driver="GPKG")
    print(f"wrote i695_osm layer: {len(i695)} ways")

    # 3. tag the MATSim network links that lie on I-695 (buffer match) -> for tolling later
    buf = i695.geometry.union_all().buffer(25)   # 25 m corridor
    onbelt = g[g.hwy.isin(["motorway","motorway_link"]) & g.geometry.intersects(buf)].copy()
    onbelt[["id","from","to","cap","hwy","geometry"]].to_file(GPKG, layer="i695_matsim_links", driver="GPKG")
    print(f"wrote i695_matsim_links: {len(onbelt):,} MATSim links on the Beltway corridor")
    onbelt[["id","from","to","cap","hwy"]].to_csv(ROOT/"input/i695_links.csv", index=False)
    print(f"wrote input/i695_links.csv ({len(onbelt)} links) for the roadpricing scenario")

if __name__=="__main__":
    main()
