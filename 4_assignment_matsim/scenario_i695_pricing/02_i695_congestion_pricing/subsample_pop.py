#!/usr/bin/env python3
"""Random subsample of the ABIT BMR population for fast ASC calibration.

ASCs are population-level constants, so a ~50k random subsample calibrates them like the full 280k but
runs fast and stays well under the plan-memory ceiling. Streams <person>...</person> blocks and keeps
each with a seeded coin flip (reproducible). Header (xml decl / DOCTYPE / <population> + any population
attributes) and footer (</population>) are preserved verbatim.

Usage: subsample_pop.py <in.xml.gz> <out.xml.gz> <target_n> [seed]
"""
import sys, gzip, random, re

inp, outp, target_n = sys.argv[1], sys.argv[2], int(sys.argv[3])
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 42

# first pass: count persons to set the keep-probability
total = 0
with gzip.open(inp, "rt") as f:
    for line in f:
        if "<person " in line:
            total += 1
p = min(1.0, target_n / total)
print(f"total persons = {total}; target = {target_n}; keep p = {p:.5f}")

rng = random.Random(seed)
kept = 0
in_person = False
buf = []
with gzip.open(inp, "rt") as f, gzip.open(outp, "wt") as g:
    header_done = False
    for line in f:
        if not in_person and "<person " not in line and not header_done:
            g.write(line)               # header lines up to the first person
            continue
        if "<person " in line:
            header_done = True
            in_person = True
            buf = [line]
            keep = rng.random() < p      # decide once per person
            continue
        if in_person:
            buf.append(line)
            if "</person>" in line:
                in_person = False
                if keep:
                    g.writelines(buf)
                    kept += 1
            continue
        # between persons (whitespace) or after last person: only footer matters
        if "</population>" in line:
            g.write(line)
print(f"kept persons = {kept}")
