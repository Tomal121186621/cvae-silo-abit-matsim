"""Build the two ABIT (activity-based travel model) composite figures for the TRB paper.

Everything is re-plotted from the ABIT validation CSVs through the shared paper_style
module so fonts/colours/legends/panel-letters match the CVAE, SILO, and MATSim exhibits.
No captions are baked into the images (captions live in LaTeX).

FIG 1  figures/abit/abit_behavior.{pdf,png}  -- 4x2 travel-behaviour validation (ABIT vs RTS)
FIG 2  figures/abit/abit_poi.{pdf,png}        -- 2-panel coordinate-assignment maps by purpose
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from PIL import Image

import paper_style as ps
ps.apply()

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .../Paper Figures Final
REPO = os.path.dirname(ROOT)                        # .../VAE-SILO-MITO-MATSIM
VAL = os.path.join(REPO, "ABIT", "validation")
OUTDIR = os.path.join(ROOT, "figures", "abit")
os.makedirs(OUTDIR, exist_ok=True)
SCRATCH = "/private/tmp/claude-501/-Users-tomal-Documents-SILO-MITO-Chayan-VAE-SILO-MITO-MATSIM/81590c65-d109-4d2a-aa09-28f4a3b1d235/scratchpad"

# ----------------------------------------------------------------------------- data
SA = pd.read_csv(os.path.join(VAL, "validation_studyarea.csv"))


def rows(metric):
    """Return dict category -> (abit, rts) for a metric block, preserving CSV order."""
    d = SA[SA.metric == metric]
    return d.set_index("category")[["abit", "rts"]]


def tvd(obs, mod):
    """Total-variation distance between the observed and modeled shares over the
    panel categories: TV = 0.5*sum|p-q|, each series normalized to sum to 1."""
    o = np.asarray(obs, float); m = np.asarray(mod, float)
    p = o / o.sum() if o.sum() else o; q = m / m.sum() if m.sum() else m
    return 0.5 * np.abs(p - q).sum()


def ttl(name, obs, mod):
    return f"{name}  (TV={tvd(obs, mod):.3f})"


# =============================================================================== FIG 1
def build_behavior():
    fig, axes = plt.subplots(3, 2, figsize=(ps.TEXTWIDTH_IN, 5.8))
    ax = axes.ravel()

    WSO = ["WORK", "SHOPPING", "OTHER"]  # disaggregate categories for the TVD

    # (a) Tour rate per traveler by purpose ----------------------------------
    d = rows("tours_per_person").loc[["WORK", "SHOPPING", "OTHER", "TOTAL"]]
    ps.grouped_bar(ax[0], ["Work", "Shop", "Other", "Total"],
                   [(ps.LAB_OBS, d["rts"].values, ps.OBS),
                    (ps.LAB_SIM, d["abit"].values, ps.SIM)],
                   title=ttl("Tour rate", d.loc[WSO, "rts"], d.loc[WSO, "abit"]),
                   ylabel="Tours per traveler", rotate=0)

    # (b) Mode share, all purposes --------------------------------------------
    modes = ["CAR_DRIVER", "CAR_PASSENGER", "TRAIN", "BUS", "WALK", "BIKE"]
    mlab = ["Car dr.", "Car pass.", "Train", "Bus", "Walk", "Bike"]
    d = rows("modeshare_all").loc[modes] * 100
    ps.grouped_bar(ax[1], mlab,
                   [(ps.LAB_OBS, d["rts"].values, ps.OBS),
                    (ps.LAB_SIM, d["abit"].values, ps.SIM)],
                   title=ttl("Mode share, all purposes", d["rts"].values, d["abit"].values),
                   ylabel="Share (%)", rotate=45)

    # (c) Mean trip length by purpose -----------------------------------------
    d = rows("triplen_mean").loc[["WORK", "SHOPPING", "OTHER", "ALL"]]
    ps.grouped_bar(ax[2], ["Work", "Shop", "Other", "All"],
                   [(ps.LAB_OBS, d["rts"].values, ps.OBS),
                    (ps.LAB_SIM, d["abit"].values, ps.SIM)],
                   title=ttl("Mean trip length", d.loc[WSO, "rts"], d.loc[WSO, "abit"]),
                   ylabel="Trip length (mi)", rotate=0)

    # (d) Departure time-of-day distribution (line plot) ----------------------
    hours = np.arange(24)
    d = rows("tod_departure_share").loc[[f"h{h:02d}" for h in hours]] * 100
    ax[3].plot(hours, d["rts"].values, color=ps.OBS, ls="--", marker="s",
               ms=2.5, lw=1.2, label=ps.LAB_OBS)
    ax[3].plot(hours, d["abit"].values, color=ps.SIM, ls="-", marker="o",
               ms=2.5, lw=1.2, label=ps.LAB_SIM)
    ax[3].set_title(ttl("Departure time-of-day", d["rts"].values, d["abit"].values))
    ax[3].set_xlabel("Departure hour")
    ax[3].set_ylabel("Share of trips (%)")
    ax[3].set_xticks(np.arange(0, 24, 3)); ax[3].set_xlim(-0.5, 23.5); ax[3].margins(x=0.02)

    # (e) Stops per tour by purpose -------------------------------------------
    d = rows("stops_per_tour").loc[["ALL", "WORK", "SHOPPING", "OTHER"]]
    ps.grouped_bar(ax[4], ["All", "Work", "Shop", "Other"],
                   [(ps.LAB_OBS, d["rts"].values, ps.OBS),
                    (ps.LAB_SIM, d["abit"].values, ps.SIM)],
                   title=ttl("Stops per tour", d.loc[WSO, "rts"], d.loc[WSO, "abit"]),
                   ylabel="Stops per tour", rotate=0)

    # (f) Median activity duration by purpose ---------------------------------
    d = rows("act_duration_median_min").loc[["WORK", "SHOPPING", "OTHER"]]
    ps.grouped_bar(ax[5], ["Work", "Shop", "Other"],
                   [(ps.LAB_OBS, d["rts"].values, ps.OBS),
                    (ps.LAB_SIM, d["abit"].values, ps.SIM)],
                   title=ttl("Median activity duration", d["rts"].values, d["abit"].values),
                   ylabel="Duration (min)", rotate=0)

    for i, a in enumerate(ax):
        ps.panel_letter(a, i)

    handles = [Patch(color=ps.OBS, label="Observed (RTS)"),
               Patch(color=ps.SIM, label="Model (ABIT)")]
    fig.legend(handles=handles, loc="upper center", ncol=2,
               bbox_to_anchor=(0.5, 1.005), frameon=False)
    fig.tight_layout(rect=[0, 0, 1, 0.975])
    fig.subplots_adjust(hspace=0.55, wspace=0.28)
    ps.save(fig, os.path.join(OUTDIR, "abit_behavior"))


# =============================================================================== FIG 2
def _prep_map(pdf_name, frac):
    """Convert a POI PDF to a caption-cropped RGB array via pdftoppm."""
    base = os.path.join(SCRATCH, pdf_name.replace(".pdf", ""))
    src = os.path.join(VAL, "TRB_figures_poi", pdf_name)
    os.system(f'pdftoppm -png -r 200 "{src}" "{base}"')
    im = Image.open(base + "-1.png").convert("RGB")
    w, h = im.size
    return np.asarray(im.crop((0, 0, w, int(h * frac))))


def build_poi():
    full = _prep_map("fig_poi_activity_map.pdf", 0.90)
    core = _prep_map("fig_poi_activity_map_core.pdf", 0.895)

    fig, axes = plt.subplots(2, 1, figsize=(ps.TEXTWIDTH_IN, 9.4))
    for a, img, ttl in zip(axes, [full, core],
                           ["Activity locations by category, full study area",
                            "Activity locations by category, Baltimore core"]):
        a.imshow(img)
        a.set_title(ttl)
        a.axis("off")
    for i, a in enumerate(axes):
        a.text(0.005, 0.995, f"({'ab'[i]})", transform=a.transAxes, va="top",
               ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout(h_pad=1.2)
    ps.save(fig, os.path.join(OUTDIR, "abit_poi"))


if __name__ == "__main__":
    build_behavior()
    build_poi()
