#!/usr/bin/env python3
"""Build a ready-styled QGIS project from baltimore_validation.gpkg so it opens clearly in one click:
   OSM basemap + full road network (categorized by hierarchy) + I-695 Beltway (bold red) + AADT
   stations graduated by GEH (green<5 / amber<10 / red). Run with QGIS's bundled python (headless)."""
import os
from qgis.core import (QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer,
                       QgsLineSymbol, QgsMarkerSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer,
                       QgsGraduatedSymbolRenderer, QgsRendererRange, QgsSymbol, QgsCoordinateReferenceSystem)

ROOT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
GPKG=f"{ROOT}/validation/gis/baltimore_validation.gpkg"
OUT=f"{ROOT}/validation/gis/baltimore_validation.qgs"

qgs=QgsApplication([], False); qgs.initQgis()
proj=QgsProject.instance()
proj.setCrs(QgsCoordinateReferenceSystem("EPSG:26985"))

def line(color,width):
    return QgsLineSymbol.createSimple({"color":color,"width":str(width)})

# OSM basemap (bottom)
osm=QgsRasterLayer("type=xyz&url=https://tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0",
                   "OpenStreetMap","wms")
if osm.isValid(): proj.addMapLayer(osm)

# road network categorized by hierarchy
net=QgsVectorLayer(f"{GPKG}|layername=road_network","Road network","ogr")
STYLE={"motorway":("#444444",0.8),"trunk":("#888","0.6"),"primary":("#999",0.5),
       "secondary":("#bbb",0.35),"tertiary":("#ccc",0.2)}
cats=[]
for val,(c,w) in STYLE.items():
    s=line(c,w); cats.append(QgsRendererCategory(val,s,val))
cats.append(QgsRendererCategory("", line("#ddd",0.2), "other"))
net.setRenderer(QgsCategorizedSymbolRenderer("hierarchy",cats))
proj.addMapLayer(net)

# I-695 bold red
i695=QgsVectorLayer(f"{GPKG}|layername=i695_osm","I-695 Beltway","ogr")
i695.setRenderer(i695.renderer().clone()); i695.renderer().setSymbol(line("#d62728",1.4))
proj.addMapLayer(i695)

# AADT stations graduated by GEH
st=QgsVectorLayer(f"{GPKG}|layername=aadt_stations","AADT stations (GEH)","ogr")
ranges=[]
for lo,hi,col,lab in [(0,5,"#2E8B57","GEH < 5 (good)"),(5,10,"#E69500","5-10 (fair)"),(10,1e9,"#C0392B",">=10 (poor)")]:
    sym=QgsMarkerSymbol.createSimple({"name":"circle","color":col,"size":"2.2","outline_style":"no"})
    ranges.append(QgsRendererRange(lo,hi,sym,lab))
gr=QgsGraduatedSymbolRenderer("GEH",ranges); gr.setClassAttribute("GEH")
st.setRenderer(gr)
proj.addMapLayer(st)

proj.write(OUT)
print("wrote",OUT)
qgs.exitQgis()
