#!/usr/bin/env python3
"""Shared helpers for the 2023 network validation (AADT daily + TMAS hourly).

Parses the MATSim *output* network (EPSG:26985, has osm:way:highway + capacity +
freespeed), joins per-link volumes from the it.64 linkstats (10% sample -> x10),
and exposes a car-link GeoDataFrame for spatial matching of count stations.
"""
import gzip, re, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
# Which MATSim run to validate. Defaults to the resident-only base run; override for the calibrated run:
#   NETVAL_OUTDIR=output_calibrated_2023 NETVAL_ITER=64 NETVAL_SUB=calibrated python validate_aadt_2023.py
_OUT = os.environ.get("NETVAL_OUTDIR", "scenarios/01_base_no_pricing/output")
_ITER = os.environ.get("NETVAL_ITER", "64")
_SUB = os.environ.get("NETVAL_SUB", "")   # validation output subdir suffix ("" = base, "calibrated" = new)
NET  = ROOT/_OUT/"output_network.xml.gz"
LINKSTATS = ROOT/_OUT/f"ITERS/it.{_ITER}/{_ITER}.linkstats.txt.gz"
SAMPLE_SCALE = 10.0   # flowCapacityFactor 0.10
CRS = "EPSG:26985"
OUTDIR = ROOT/("network_validation_2023" if not _SUB else f"network_validation_2023/{_SUB}")

# FHWA functional class (F_SYSTEM) -> facility group used for reporting.
FSYS_GROUP = {1:"Interstate/Freeway", 2:"Interstate/Freeway",
              3:"Principal Arterial", 4:"Minor Arterial",
              5:"Collector/Local", 6:"Collector/Local", 7:"Collector/Local"}
GROUP_ORDER = ["Interstate/Freeway","Principal Arterial","Minor Arterial","Collector/Local"]

# F_SYSTEM -> permissible OSM highway classes (so an interstate count matches the
# freeway mainline, not a parallel surface street, and vice-versa).
FSYS_HWY = {
    1: {"motorway","motorway_link","trunk"},
    2: {"motorway","trunk","motorway_link","trunk_link","primary"},
    3: {"trunk","primary","secondary","trunk_link","primary_link"},
    4: {"primary","secondary","tertiary","primary_link","secondary_link"},
    5: {"secondary","tertiary","residential","unclassified","tertiary_link"},
    6: {"tertiary","residential","unclassified","secondary","living_street"},
    7: {"residential","unclassified","tertiary","living_street","service"},
}
FSYS_TOL = {1:80.0, 2:75.0, 3:55.0, 4:45.0, 5:40.0, 6:40.0, 7:40.0}

# ---------------------------------------------------------------- network parsing
def parse_network():
    """Return nodes{id:(x,y)} and car links[{id,from,to,cap,freespeed,hwy}]."""
    nodes={}; links=[]
    nre=re.compile(r'<node id="([^"]+)" x="([^"]+)" y="([^"]+)"')
    lstart=re.compile(r'<link id="([^"]+)" from="([^"]+)" to="([^"]+)"[^>]*?freespeed="([^"]+)"[^>]*?capacity="([^"]+)"[^>]*?modes="([^"]+)"')
    hw=re.compile(r'osm:way:highway" class="java.lang.String">([^<]+)<')
    cur=None
    with gzip.open(NET,"rt") as f:
        for line in f:
            m=nre.search(line)
            if m: nodes[m.group(1)]=(float(m.group(2)),float(m.group(3))); continue
            m=lstart.search(line)
            if m:
                if "car" in m.group(6).split(","):
                    cur={"id":m.group(1),"from":m.group(2),"to":m.group(3),
                         "freespeed":float(m.group(4)),"cap":float(m.group(5)),"hwy":""}
                else: cur=None
                continue
            if cur is not None:
                hm=hw.search(line)
                if hm: cur["hwy"]=hm.group(1)
                if "</link>" in line:
                    links.append(cur); cur=None
    return nodes, links

def load_linkstats():
    """Per-link 24h + hourly avg volumes from linkstats, scaled x10. Indexed by str LINK id."""
    df=pd.read_csv(LINKSTATS, sep="\t", dtype={"LINK":str})
    hrcols=[f"HRS{h}-{h+1}avg" for h in range(24)]
    keep=["LINK","HRS0-24avg"]+hrcols
    df=df[keep].copy()
    df["vol24"]=df["HRS0-24avg"]*SAMPLE_SCALE
    for h in range(24):
        df[f"h{h}"]=df[f"HRS{h}-{h+1}avg"]*SAMPLE_SCALE
    return df.set_index("LINK")

def link_gdf():
    """Car-link GeoDataFrame with vol24, hourly h0..h23, unit direction vector."""
    import geopandas as gpd
    from shapely.geometry import LineString
    nodes, links = parse_network()
    ls = load_linkstats()
    rows=[]
    for l in links:
        if l["from"] not in nodes or l["to"] not in nodes: continue
        a=nodes[l["from"]]; b=nodes[l["to"]]
        lid=l["id"]
        rec={**l,"fx":a[0],"fy":a[1],"tx":b[0],"ty":b[1],"geometry":LineString([a,b])}
        if lid in ls.index:
            r=ls.loc[lid]
            rec["vol24"]=float(r["vol24"])
            for h in range(24): rec[f"h{h}"]=float(r[f"h{h}"])
        else:
            rec["vol24"]=0.0
            for h in range(24): rec[f"h{h}"]=0.0
        rows.append(rec)
    g=gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)
    dx=g.tx-g.fx; dy=g.ty-g.fy; ln=np.hypot(dx,dy).replace(0,1)
    g["ux"]=dx/ln; g["uy"]=dy/ln
    return g

def geh(model, obs):
    model=np.asarray(model,float); obs=np.asarray(obs,float)
    with np.errstate(divide="ignore",invalid="ignore"):
        g=np.sqrt(2*(model-obs)**2/(model+obs))
    return np.where((model+obs)>0, g, np.nan)
