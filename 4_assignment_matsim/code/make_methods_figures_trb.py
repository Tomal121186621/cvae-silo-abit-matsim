#!/usr/bin/env python3
"""Clean, de-ornamented re-render of the two MATSim METHODS figures for the paper:
  1. income_vot_modechoice  — the income-dependent value-of-time mode-choice formulation
  2. pipeline_feedback      — the VAE -> SILO -> ABIT <-> MATSim feedback-loop diagram

STYLING ONLY. Every number/parameter is identical to the original docs/ PNGs:
  lambda = 0.6 ; clip [0.4, 2.5] ; I_ref = $7,018/mo ; VOT_ref = car 30 / shared 40 / transit 15 $/h.

The original docs/*.png were ornamented (bold titles, a rounded accent 'equity'
box, an accent-blue #1f4e79, heavy arrows, DejaVu-only). This version uses the
shared trb_style: single sans-serif font + sizes, SIM-blue / neutral-gray only,
thin lines, no boxes/gradients/shadows. Explanatory text goes in the caption.
"""
import sys
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle
sys.path.insert(0, "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/code")
import trb_style; trb_style.apply()

DOCS = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim/docs")
OUT = DOCS / "TRB_figures"; OUT.mkdir(parents=True, exist_ok=True)

I_REF = 7.018          # region-median household income, $1000 / month  (= $7,018/mo)
LAM = 0.6              # income elasticity of VOT
CLIP_LO, CLIP_HI = 0.4, 2.5

# ======================================================================= FIG 1
def income_vot():
    fig = plt.figure(figsize=trb_style.size(trb_style.COL2, 0.52))
    gsL = fig.add_axes([0.02, 0.05, 0.50, 0.90]); gsL.axis("off")
    ax = fig.add_axes([0.63, 0.16, 0.34, 0.74])

    eqs = [
        (r"(1)  Mode choice — multinomial logit over the 7 modes:",
         r"$P_{n,m} = \dfrac{\exp(U_{n,m})}{\sum_j \exp(U_{n,j})}$"),
        (r"(2)  Utility of mode $m$ for agent $n$:",
         r"$U_{n,m} = ASC_m + \boldsymbol{\beta}^{\top}\mathbf{x}_n + \beta_{GC}\,GC_{n,m}$"),
        (r"(3)  Generalized cost (minutes):",
         r"$GC_{n,m} = t_{n,m} + \dfrac{60\,c_{n,m}}{VOT_m(I_n)}$"),
        (r"(4)  Continuous income-dependent VOT (per agent):",
         r"$VOT_m(I_n) = VOT_m^{ref}\cdot \mathrm{clip}\!\left[\left(\dfrac{I_n}{I_{ref}}\right)^{\lambda},\,0.4,\,2.5\right]$"),
    ]
    y = 0.97
    for head, eq in eqs:
        gsL.text(0.0, y, head, ha="left", va="top", fontsize=8.5, transform=gsL.transAxes)
        gsL.text(0.06, y - 0.055, eq, ha="left", va="top", fontsize=11, transform=gsL.transAxes)
        y -= 0.205
    gsL.text(0.0, y + 0.02,
             r"where $\mathbf{x}_n$: socio-demographics ($\beta$ estimated from the RTS);"
             "\n"
             r"$c_{n,m}$: cost \$ = distance$\times$\$0.20 + toll (full on car-driver, half"
             "\nshared-ride);  "
             r"$I_n$: monthly income;  $I_{ref}=\$7{,}018$/mo;  $\lambda=0.6$;"
             "\n"
             r"$VOT^{ref}=$ car 30 / shared-ride 40 / transit 15 \$/h.",
             ha="left", va="top", fontsize=7.4, transform=gsL.transAxes)

    x = np.linspace(0.2, 30, 400)
    factor = np.clip((x / I_REF) ** LAM, CLIP_LO, CLIP_HI)
    ax.plot(x, factor, color=trb_style.SIM, lw=1.6, zorder=4)
    ax.axhline(CLIP_HI, color=trb_style.NEUTRAL, ls="--", lw=0.9, zorder=2)
    ax.axhline(CLIP_LO, color=trb_style.NEUTRAL, ls="--", lw=0.9, zorder=2)
    ax.axvline(I_REF, color=trb_style.NEUTRAL, ls=":", lw=0.8, zorder=2)
    ax.plot([I_REF], [1.0], "o", color=trb_style.SIM, ms=5, zorder=5)
    ax.annotate("clip 2.5 (high income)", (0.5, CLIP_HI), textcoords="offset points",
                xytext=(2, 3), fontsize=6.8, color=trb_style.NEUTRAL, ha="left", va="bottom")
    ax.annotate("clip 0.4 (low income)", (0.5, CLIP_LO), textcoords="offset points",
                xytext=(2, 3), fontsize=6.8, color=trb_style.NEUTRAL, ha="left", va="bottom")
    ax.annotate("median income\nfactor = 1.0", (I_REF, 1.0), textcoords="offset points",
                xytext=(8, -2), fontsize=6.8, color=trb_style.NEUTRAL, ha="left", va="top")
    ax.set_xlim(0, 30); ax.set_ylim(0, 2.7)
    ax.set_xlabel("household income  ($1000 / month)")
    ax.set_ylabel(r"VOT factor  $(I_n/I_{ref})^{0.6}$")
    trb_style.finalize(ax, grid_axis="y")
    ax.set_title("Per-agent VOT multiplier", loc="left")

    cap = ("Figure. Income-dependent value-of-time (VOT) mode choice. The 7-mode "
           "generalized-cost logit (Chayan & Cirillo, 2024) is extended with a "
           "continuous per-agent income term: VOT scales with (I/I_ref)^0.6, clipped "
           "to [0.4, 2.5] and equal to 1.0 at the region-median income ($7,018/mo). "
           "Lower income -> lower VOT -> the toll's dollar cost weighs more in utility "
           "-> a larger mode shift away from the tolled car; at the median the base "
           "split is preserved.")
    trb_style.save(fig, OUT / "income_vot_modechoice_slide", caption_text=cap)
    print("wrote", OUT / "income_vot_modechoice_slide.png")


# ======================================================================= FIG 2
def pipeline_feedback():
    fig = plt.figure(figsize=trb_style.size(trb_style.COL2, 0.62))
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0]); ax.axis("off")
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)

    def box(x, y, w, h, title, sub, edge="#333333"):
        ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor=edge, linewidth=0.9))
        ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", fontsize=10)
        if sub:
            ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", fontsize=7.2,
                    color=trb_style.NEUTRAL)

    def arrow(x0, y0, x1, y1, color="#333333", lw=1.1):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                     mutation_scale=9, color=color, lw=lw,
                                     shrinkA=0, shrinkB=0))

    # top row: VAE -> SILO -> ABIT <-> MATSim
    yb, hb = 78, 16
    box(2, yb, 18, hb, "VAE", "Synthetic\npopulation")
    box(28, yb, 18, hb, "SILO", "Land use\n(2023)")
    box(54, yb, 20, hb, "ABIT", "Activity-based demand\n+ income-VOT mode choice", edge=trb_style.SIM)
    box(82, yb, 16, hb, "MATSim", "Traffic assignment\n+ I-695 toll", edge=trb_style.SIM)

    arrow(20, yb + hb / 2, 28, yb + hb / 2)
    arrow(46, yb + hb / 2, 54, yb + hb / 2)
    # feedback loop between ABIT and MATSim (semantic SIM blue)
    arrow(74, yb + hb * 0.62, 82, yb + hb * 0.62, color=trb_style.SIM, lw=1.3)
    arrow(82, yb + hb * 0.30, 74, yb + hb * 0.30, color=trb_style.SIM, lw=1.3)
    ax.text(78, yb + hb + 3, "plans + mode split", ha="center", va="bottom",
            fontsize=7.6, color=trb_style.SIM)
    ax.text(78, yb - 3, "congested + tolled skims", ha="center", va="top",
            fontsize=7.6, color=trb_style.SIM)

    # inside-ABIT chain (dashed enclosure, thin)
    ax.add_patch(Rectangle((2, 50), 72, 20, fill=False, edgecolor=trb_style.NEUTRAL,
                           linewidth=0.7, linestyle=(0, (4, 3))))
    ax.text(4, 67.5, "Inside ABIT (agent-based activity model)", ha="left", va="center", fontsize=8)
    steps = ["Tour\nfrequency", "Destination\nchoice", "Mode\nchoice", "Stops &\nsubtours", "Schedule\n(TOD)"]
    sx, sw, sgap = 5, 11.5, 2.0
    for i, s in enumerate(steps):
        bx = sx + i * (sw + sgap)
        ax.add_patch(Rectangle((bx, 54), sw, 8, fill=False, edgecolor="#333333", linewidth=0.8))
        ax.text(bx + sw / 2, 58, s, ha="center", va="center", fontsize=7.0)
        if i < len(steps) - 1:
            arrow(bx + sw, 58, bx + sw + sgap, 58)
    ax.text(4, 51.5, "7-mode generalized-cost mode choice (Chayan & Cirillo, 2024) . "
            "income-dependent VOT . real-POI locations . RTS-calibrated",
            ha="left", va="center", fontsize=6.8, color=trb_style.NEUTRAL)
    ax.text(87, 60, "Feedback loop —\nrepeat until the\nmode split converges\n(3-5 iterations)",
            ha="center", va="center", fontsize=7.6, style="italic", color=trb_style.NEUTRAL)

    # algorithm steps (plain text, NO rounded ornamental box)
    ax.text(2, 44, "Feedback-loop algorithm", ha="left", va="top", fontsize=9)
    algo = [
        "0   ABIT builds base daily plans from SILO / VAE — tours, POI-based activity locations, income-VOT mode choice on free-flow skims.",
        "1   MATSim assigns the plans on the tolled network; its inner loop re-routes and re-times trips (modes held fixed).",
        "2   Extract updated origin-destination skims from MATSim: congested car travel time + per-OD toll cost.",
        "3   ABIT re-runs its income-VOT generalized-cost mode choice on the new skims to produce an updated mode split.",
        "4   If the mode split changed by less than the tolerance, stop; otherwise return to Step 1.",
    ]
    yy = 39
    for line in algo:
        ax.text(3, yy, line, ha="left", va="top", fontsize=7.8)
        yy -= 6.5
    ax.text(2, yy - 1.5, "Outputs:  mode shift . toll revenue . consumer surplus (equity) by income / race / age . departure-time shift.",
            ha="left", va="top", fontsize=7.8)

    cap = ("Figure. Coupled VAE -> SILO -> ABIT <-> MATSim pipeline. ABIT (activity-based "
           "demand with income-VOT mode choice) and MATSim (traffic assignment with the "
           "I-695 toll) iterate: ABIT sends plans + mode split, MATSim returns congested, "
           "tolled skims, and the loop repeats until the mode split converges.")
    trb_style.save(fig, OUT / "pipeline_feedback_diagram", caption_text=cap)
    print("wrote", OUT / "pipeline_feedback_diagram.png")


if __name__ == "__main__":
    income_vot()
    pipeline_feedback()
