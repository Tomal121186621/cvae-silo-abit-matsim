#!/usr/bin/env python3
"""Restore the I-83 mainline connection to the study-area boundary (PA line).

The Maryland OSM extract clips the I-83 (Harrisburg Expressway) mainline ~1.6-2.3 km
short of the state line (NB carriageway ends at node 317688328, y=226,380; SB begins
at node 317687810, y=225,743), so no motorway crosses the northern boundary and the
I-83 gateway could only match the parallel York Road. Mirrors add_keybridge_v14.py:
adds one boundary node on the I-83 alignment just beyond the state line and one
motorway link per direction connecting the dangling carriageway ends.
  i83_nb_stub: 317688328 -> i83_border  (~1.75 km)
  i83_sb_stub: i83_border -> 317687810  (~2.45 km)
2 lanes/dir @ 2000 veh/h/lane, 65 mph (facility standard).
Usage: add_i83_border_stub.py <src.xml.gz> <dst.xml.gz>
"""
import gzip, sys
import xml.etree.ElementTree as ET

SRC, DST = sys.argv[1], sys.argv[2]
FS = 65 / 2.237                      # 65 mph in m/s
BX, BY = 430300.0, 228050.0          # boundary node, on the I-83 alignment past the line
NB_END, SB_START = "317688328", "317687810"

tree = ET.parse(gzip.open(SRC, "rb"))
root = tree.getroot()
nodes_el = root.find("nodes")
links_el = root.find("links")

bnode = ET.SubElement(nodes_el, "node", {"id": "i83_border", "x": f"{BX}", "y": f"{BY}"})
bnode.tail = "\n"
modes = next(l.get("modes") for l in links_el.iter("link") if l.get("id") == "275004")
NEW = [("i83_nb_stub", NB_END, "i83_border", 1750.0),
       ("i83_sb_stub", "i83_border", SB_START, 2450.0)]
for lid, f_, t_, length in NEW:
    l = ET.SubElement(links_el, "link", {
        "id": lid, "from": f_, "to": t_, "length": f"{length:.1f}",
        "freespeed": f"{FS:.4f}", "capacity": "4000", "permlanes": "2",
        "oneway": "1", "modes": modes})
    attrs = ET.SubElement(l, "attributes")
    a = ET.SubElement(attrs, "attribute", {"name": "osm:way:highway", "class": "java.lang.String"})
    a.text = "motorway"
    l.tail = "\n"
    attrs.tail = "\n"
    a.tail = "\n"

with gzip.open(DST, "wb") as f:
    f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE network SYSTEM "http://www.matsim.org/files/dtd/network_v2.dtd">\n')
    tree.write(f, encoding="utf-8", xml_declaration=False)
print("wrote", DST)
