#!/usr/bin/env python3
"""Clean Maryland-only year-to-year validation figure: SILO-vs-ACS Total Variation
per variable across 2016-2023, calibration (2016-20) vs out-of-sample forecast (2021-23).
Output → validation/by_year_acs_calib5/figures/md_year_to_year.png
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import sys; sys.path.insert(0, "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/code")
import trb_style; trb_style.apply()

ROOT = Path(__file__).resolve().parents[1]
VDIR = ROOT / "validation" / "by_year_acs_calib5"
OUT = VDIR / "TRB_figures" / "md_year_to_year"
YEARS = list(range(2016, 2024))

LABELS = {"hhSize": "Household size", "autos": "Autos", "dwellingType": "Dwelling type",
          "hh_inc9": "Household income", "age_bin": "Age", "gender": "Gender",
          "occ_silo": "Occupation", "race4": "Race"}
ORDER = ["age_bin", "occ_silo", "autos", "hhSize", "dwellingType", "race4", "hh_inc9", "gender"]

rows = []
for y in YEARS:
    f = VDIR / str(y) / "metrics_MD.csv"
    if f.exists():
        rows.append(pd.read_csv(f))
df = pd.concat(rows, ignore_index=True)
df = df[df["variable"].isin(LABELS)]

fig, ax = plt.subplots(figsize=trb_style.size(trb_style.COL2, 0.52))
# forecast region shading (2021-2023 out-of-sample)
ax.axvspan(2020.5, 2023.5, color=trb_style.NEUTRAL, alpha=0.07, zorder=0)

for k, v in enumerate(ORDER):
    d = df[df["variable"] == v].sort_values("year")
    ax.plot(d["year"], d["tv"], marker=trb_style.MARKERS[k % len(trb_style.MARKERS)],
            ls=trb_style.LINESTYLES[k % len(trb_style.LINESTYLES)],
            color=trb_style.PALETTE[k % len(trb_style.PALETTE)], label=LABELS[v])

ax.axvline(2020.5, color=trb_style.NEUTRAL, ls="--", lw=1)
ax.set_xlabel("Year")
ax.set_ylabel("Total variation (SILO vs. ACS PUMS)")
ax.set_xticks(YEARS)
ax.set_ylim(bottom=0)
ax.grid(True, axis="y")
# annotate the two regions
ymax = ax.get_ylim()[1]
ax.text(2018, ymax * 0.96, "CALIBRATION", ha="center", va="top", fontsize=8, color="0.35")
ax.text(2022, ymax * 0.96, "FORECAST (out-of-sample)", ha="center", va="top", fontsize=8, color="0.35")
ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
cap = ("Figure 3. Maryland year-to-year validation, 2016–2023: total variation between "
       "SILO and ACS PUMS by attribute; calibration 2016–2020 vs. out-of-sample "
       "forecast 2021–2023 (shaded).")
trb_style.save(fig, OUT, caption_text=cap)
print(f"saved → {OUT}")
print(df.pivot_table(index="variable", columns="year", values="tv").round(3).to_string())
