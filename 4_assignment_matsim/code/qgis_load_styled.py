# Run inside QGIS:  QGIS --code qgis_load_styled.py
# Loads the Baltimore validation layers, styled, onto an OSM basemap, and saves the project.
from qgis.core import (QgsProject, QgsVectorLayer, QgsRasterLayer, QgsLineSymbol, QgsMarkerSymbol,
                       QgsCategorizedSymbolRenderer, QgsRendererCategory,
                       QgsGraduatedSymbolRenderer, QgsRendererRange, QgsCoordinateReferenceSystem)

ROOT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
G=f"{ROOT}/validation/gis/baltimore_validation.gpkg"
V=f"{ROOT}/validation/gis/qgis_validation.gpkg"
proj=QgsProject.instance()

def line(color,w):
    return QgsLineSymbol.createSimple({"color":color,"width":str(w)})

# OSM basemap
osm=QgsRasterLayer("type=xyz&url=https://tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0",
                   "OpenStreetMap","wms")
if osm.isValid(): proj.addMapLayer(osm)

# road network by hierarchy
net=QgsVectorLayer(f"{G}|layername=road_network","Road network","ogr")
if net.isValid():
    STY={"motorway":("#404040",0.7),"trunk":("#707070",0.5),"primary":("#909090",0.4),
         "secondary":("#b0b0b0",0.3),"tertiary":("#d0d0d0",0.18)}
    cats=[QgsRendererCategory(k,line(c,w),k) for k,(c,w) in STY.items()]
    cats.append(QgsRendererCategory("",line("#e0e0e0",0.15),"other"))
    net.setRenderer(QgsCategorizedSymbolRenderer("hierarchy" if net.fields().indexOf("hierarchy")>=0 else "hwy",cats))
    proj.addMapLayer(net)

# I-695 bold red
i695=QgsVectorLayer(f"{G}|layername=i695_osm","I-695 Beltway","ogr")
if i695.isValid():
    i695.renderer().setSymbol(line("#d62728",1.6)); proj.addMapLayer(i695)

# validated stations graduated by GEH (matching done by QGIS native join)
st=QgsVectorLayer(f"{V}|layername=stations_validated","AADT validation (GEH)","ogr")
if st.isValid():
    rng=[]
    for lo,hi,col,lab in [(0,5,"#2E8B57","GEH < 5 (good)"),(5,10,"#E69500","5-10 (fair)"),(10,1e9,"#C0392B",">=10 (poor)")]:
        sym=QgsMarkerSymbol.createSimple({"name":"circle","color":col,"size":"2.4","outline_style":"no"})
        rng.append(QgsRendererRange(lo,hi,sym,lab))
    gr=QgsGraduatedSymbolRenderer("GEH",rng); st.setRenderer(gr); proj.addMapLayer(st)

proj.write(f"{ROOT}/validation/gis/baltimore_validation.qgs")
try:
    from qgis.utils import iface
    if st.isValid(): iface.mapCanvas().setExtent(st.extent()); iface.mapCanvas().refresh()
except Exception: pass
print("LOADED Baltimore validation project")
