#!/usr/bin/env python3
"""Component 3 helper -- scale per-link `capacity` by a per-facility factor.

Usage:  edit_network_capacity.py <in_net.xml.gz> <caps.json> <out_net.xml.gz>

caps.json = {"freeway":1.0,"principal":0.67,"minor":1.0,"collector":1.0,"ramp":1.0}
Each factor multiplies the link `capacity` attribute for links of that facility.
Facility is classified from the link's `osm:way:highway` child attribute, exactly the
way the network audit did (freeway=motorway, principal=trunk/primary, minor=secondary,
collector=tertiary, ramp=*_link). Links whose facility is not in caps.json (local
streets: residential/unclassified/service/...) are written unchanged.

The network stores `capacity` in the <link ...> opening tag but `osm:way:highway` in a
child <attribute>, so each link block is buffered, the highway read, then the opening
tag's capacity rewritten. Output is gzipped.
"""
import gzip, json, re, sys
from collections import Counter

# osm:way:highway -> facility bucket (matches network_audit classification)
FAC_BY_HWY = {
    "motorway": "freeway",
    "trunk": "principal", "primary": "principal",
    "secondary": "minor",
    "tertiary": "collector",
    "motorway_link": "ramp", "trunk_link": "ramp",
    "primary_link": "ramp", "secondary_link": "ramp", "tertiary_link": "ramp",
}
CAP_RE = re.compile(r'(capacity=")([0-9.eE+\-]+)(")')
HWY_RE = re.compile(r'osm:way:highway"[^>]*>([^<]+)<')


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: edit_network_capacity.py <in_net.xml.gz> <caps.json> <out_net.xml.gz>")
    in_net, caps_path, out_net = sys.argv[1:4]
    caps = json.load(open(caps_path))
    nchg = Counter(); ncap = Counter()

    def rewrite(open_line, hwy):
        fac = FAC_BY_HWY.get((hwy or "").strip())
        factor = caps.get(fac, 1.0) if fac else 1.0
        ncap[fac or "local"] += 1
        if factor == 1.0:
            return open_line
        def sub(m):
            return f"{m.group(1)}{float(m.group(2))*factor:.1f}{m.group(3)}"
        new = CAP_RE.sub(sub, open_line, count=1)
        if new != open_line:
            nchg[fac] += 1
        return new

    op = gzip.open if in_net.endswith(".gz") else open
    oop = gzip.open if out_net.endswith(".gz") else open
    with op(in_net, "rt") as fin, oop(out_net, "wt") as fout:
        in_link = False; buf = []; hwy = None
        for line in fin:
            if "<link " in line:
                # self-closing single-line link (no child attributes) -> local, unchanged
                if "/>" in line and "</link>" not in line:
                    fout.write(rewrite(line, None)); continue
                in_link = True; buf = [line]; hwy = None; continue
            if in_link:
                buf.append(line)
                m = HWY_RE.search(line)
                if m: hwy = m.group(1)
                if "</link>" in line:
                    buf[0] = rewrite(buf[0], hwy)
                    fout.writelines(buf)
                    in_link = False; buf = []
                continue
            fout.write(line)

    print("caps applied:", json.dumps(caps))
    print("links seen per facility:", dict(ncap))
    print("links whose capacity changed:", dict(nchg))
    print("wrote", out_net)


if __name__ == "__main__":
    main()
