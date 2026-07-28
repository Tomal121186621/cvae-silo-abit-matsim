#!/usr/bin/env python3
"""Regional map of the AADT count stations, with the RADIAL inflow/outflow gateway
crossings highlighted — the stations used to check total flow into/out of the region.

Why these points: the v7 demand is RESIDENT-ONLY (no external/through trips), so the
honest check on regional inflow/outflow is a RADIAL SCREENLINE — the count stations
sitting on the major limited-access + arterial corridors where traffic enters/leaves
the Baltimore region (I-95 SW & NE, I-83 N, I-70 W, US-40 W & E, MD-295 S, I-795 NW,
I-97 S, MD-140 NW, MD-26 W, MD-2 S, MD-43 NE, MD-144 W). These 14 are RADIAL crossings,
NOT a closed beltway cordon. The gateway set is exactly validate_base_hybrid.NAMED+EXTRA.

Outputs into network_validation_2023/v7_base/:
  gateway_stations_map.{png,pdf}         — the map figure (300 dpi + vector)
  gis/aadt_stations_all.shp              — every matched station (role/facility fields)
  gis/gateway_stations.shp               — the 14 radial gateway crossings (route/dir)
"""
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import Point
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
V7   = ROOT/"network_validation_2023/v7_base"
AADT = ROOT/"network_validation_2023/transitfix/aadt/aadt_validation_2023_cleaned.csv"
GPKG = V7/"gis/bmr_validation.gpkg"
CRS  = "EPSG:26985"
GIS  = V7/"gis"; GIS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.family":"serif","font.serif":["Times New Roman","Times","DejaVu Serif"],
    "font.size":12,"axes.titlesize":16,"axes.labelsize":12,"xtick.labelsize":10,"ytick.labelsize":10,
    "savefig.dpi":300,"figure.dpi":120})

# --- the RADIAL inflow/outflow gateway crossings (validate_base_hybrid NAMED + EXTRA) --------------
GATEWAYS = {
    "B2532":("I-95","SW"),  "B0988":("I-95","NE"),  "P0052":("I-83","N"),  "P0053":("I-70","W"),
    "B0945":("US-40","W"),  "B1202":("US-40","E"),  "B0717":("MD-295","S"),
    "B030066":("I-795","NW"),"B0628":("I-97","S"),  "B1024":("MD-140","NW"),"B0939":("MD-26","W"),
    "B0617":("MD-2","S"),   "B030058":("MD-43","NE"),"B1033":("MD-144","W"),
}

d = pd.read_csv(AADT)
d["LOCATION_ID"] = d.LOCATION_ID.astype(str)
d["role"]  = np.where(d.LOCATION_ID.isin(GATEWAYS), "gateway", "interior")
d["gw_route"] = d.LOCATION_ID.map(lambda x: GATEWAYS.get(x,("",""))[0])
d["gw_dir"]   = d.LOCATION_ID.map(lambda x: GATEWAYS.get(x,("",""))[1])
gdf = gpd.GeoDataFrame(d, geometry=[Point(xy) for xy in zip(d.lon, d.lat)], crs=CRS)

# --- shapefiles (GIS-usable) ---------------------------------------------------------------------
shp_cols = ["LOCATION_ID","ROADNAME","facility","F_SYSTEM","obs_AADT","role","gw_route","gw_dir","geometry"]
gdf[shp_cols].to_file(GIS/"aadt_stations_all.shp")
gdf[gdf.role=="gateway"][shp_cols].to_file(GIS/"gateway_stations.shp")
print("wrote shapefiles:", GIS/"aadt_stations_all.shp", "+", GIS/"gateway_stations.shp")

# --- map extent: tight around the gateways + regional context margin -----------------------------
gwpts = gdf[gdf.role=="gateway"]
gminx, gminy, gmaxx, gmaxy = gwpts.total_bounds
mx = (gmaxx-gminx)*0.55; my = (gmaxy-gminy)*0.45
minx, maxx = gminx-mx, gmaxx+mx
miny, maxy = gminy-my, gmaxy+my

# --- county boundaries for context ---------------------------------------------------------------
try:
    cty = gpd.read_file(GPKG, layer="county_boundaries").to_crs(CRS)
except Exception as e:
    cty = None; print("county layer unavailable:", e)

# --- OSM / MATSim road network (lines), clipped to the view bbox ----------------------------------
print("reading network layer (bbox-clipped) ...")
net = gpd.read_file(GPKG, layer="network", bbox=(minx, miny, maxx, maxy))
try: net = net.to_crs(CRS)
except Exception: pass
hw = net.highway.astype(str)
FREEWAY  = {"motorway","motorway_link","trunk","trunk_link"}
ARTERIAL = {"primary","primary_link","secondary","secondary_link"}
net_free = net[hw.isin(FREEWAY)]
net_art  = net[hw.isin(ARTERIAL)]
net_min  = net[~hw.isin(FREEWAY|ARTERIAL)]
print(f"network in view: {len(net)} links ({len(net_free)} freeway, {len(net_art)} arterial, {len(net_min)} minor)")

fig, ax = plt.subplots(figsize=(14.5, 10.5))
if cty is not None:
    cty.plot(ax=ax, facecolor="#F5F2EA", edgecolor="#9E968400", linewidth=0.0, zorder=0)
net_min.plot(ax=ax, color="#C9CDD2", linewidth=0.18, zorder=1)
net_art.plot(ax=ax, color="#8FA0B3", linewidth=0.45, zorder=2)
net_free.plot(ax=ax, color="#37546F", linewidth=1.2, zorder=3)
if cty is not None:   # county borders ON TOP of the network web
    cty.boundary.plot(ax=ax, color="#7A7160", linewidth=1.1, zorder=4)

# proxy legend handles for the line layers
from matplotlib.lines import Line2D
net_handles = [
    Line2D([0],[0], color="#37546F", lw=2.0, label="Freeway / interstate (OSM motorway·trunk)"),
    Line2D([0],[0], color="#8FA0B3", lw=1.4, label="Arterial (primary·secondary)"),
    Line2D([0],[0], color="#C9CDD2", lw=1.2, label="Minor road / local"),
    Line2D([0],[0], color="#7A7160", lw=1.4, label="County boundary"),
]

gw = gdf[gdf.role=="gateway"]
ax.scatter(gw.geometry.x, gw.geometry.y, s=430, marker="*", c="#B01B2E",
           edgecolors="white", linewidth=1.4, zorder=5,
           label=f"Radial inflow/outflow gateway (n={len(gw)})")
# labels: route + compass direction on a leader line. Default push is the compass direction; the
# crowded Baltimore-core / southern stations get explicit (dx,dy,length) overrides so nothing overlaps.
DIROFF = {"N":(0,1),"S":(0,-1),"E":(1,0),"W":(-1,0),"NE":(1,1),"NW":(-1,1),"SE":(1,-1),"SW":(-1,-1)}
OVERRIDE = {  # station_id : (dx, dy, leader_len_pts)
    "B0717":(-1.6,-0.9,72), "B0628":(0.1,-1.5,96), "B0617":(1.6,-0.9,72),   # MD-295/I-97/MD-2 (southern trio)
    "B2532":(-1.7,-0.2,64),                                                  # I-95 SW
    "B030066":(-1.7,0.5,70), "B1024":(-1.1,1.4,74),                          # I-795 / MD-140 (NW pair)
    "B0988":(1.5,0.7,66), "B030058":(1.5,1.2,66), "B1202":(1.7,0.1,64),      # I-95 NE / MD-43 NE / US-40 E
    "P0052":(0.0,1.4,70), "P0053":(-1.6,0.2,66), "B0945":(-1.6,-0.2,66),     # I-83 N / I-70 W / US-40 W
    "B0939":(-1.6,0.6,66), "B1033":(-1.6,-0.6,72),                           # MD-26 W / MD-144 W
}
BASE_L = 52
for _, r in gw.iterrows():
    if r.LOCATION_ID in OVERRIDE:
        dx, dy, Lp = OVERRIDE[r.LOCATION_ID]
    else:
        dx, dy = DIROFF.get(r.gw_dir, (1,1)); Lp = BASE_L
    ax.annotate(f"{r.gw_route} ({r.gw_dir})", (r.geometry.x, r.geometry.y),
                xytext=(dx*Lp, dy*Lp), textcoords="offset points", fontsize=11, weight="bold",
                color="#111111", ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#B01B2E", lw=0.9, alpha=0.95),
                arrowprops=dict(arrowstyle="-", lw=0.8, color="#8A2432"), zorder=6)

# zoom to the gateway-focused view bbox computed above
ax.set_xlim(minx, maxx); ax.set_ylim(miny, maxy)
ax.set_title("MATSim road network, county boundaries, and radial inflow/outflow gateways — Baltimore Region")
ax.set_xlabel("Easting [m, EPSG:26985]"); ax.set_ylabel("Northing [m]")
ax.set_aspect("equal")
gw_handle = Line2D([0],[0], marker="*", color="none", markerfacecolor="#B01B2E",
                   markeredgecolor="white", markersize=20, label=f"Radial inflow/outflow gateway (n={len(gw)})")
ax.legend(handles=net_handles+[gw_handle], loc="center left", bbox_to_anchor=(1.01, 0.5),
          framealpha=0.95, fontsize=12, title="Legend", title_fontsize=12.5)
fig.text(0.5, 0.045,
         "Gateways = the 14 radial-corridor crossings used as the regional in/out screenline (I-95, I-83, I-70, "
         "US-40, MD-295, I-795, I-97, MD-140, MD-26, MD-2, MD-43, MD-144). Radial crossings, NOT a closed beltway cordon.",
         ha="center", va="top", fontsize=8.5, style="italic", color="0.30")
fig.savefig(V7/"gateway_stations_map.png", bbox_inches="tight", dpi=300)
fig.savefig(V7/"gateway_stations_map.pdf", bbox_inches="tight"); plt.close(fig)
print("wrote map ->", V7/"gateway_stations_map.png")
