"""Platform architecture diagram (Figure 1) drawn through the shared paper_style."""
import os, sys
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paper_style as ps
ps.apply()
OUT = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Paper Figures Final/figures"

fig, ax = plt.subplots(figsize=(ps.TEXTWIDTH_IN, 3.5))
ax.set_xlim(0, 100); ax.set_ylim(0, 56); ax.axis("off")

STAGE = "#0072B2"; DATA = "#4D4D4D"; EXT = "#009E73"; POLICY = "#D55E00"


def box(x, y, w, h, text, fc, tc="white", fs=8.2, ls="-", ec=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=1.2,rounding_size=2.5",
                 linewidth=1.1, facecolor=fc, edgecolor=ec or fc, linestyle=ls))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tc,
            fontsize=fs, fontweight="bold", wrap=True)


def arrow(x1, y1, x2, y2, color="#333333", lw=1.6, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                 mutation_scale=12, linewidth=lw, color=color, shrinkA=0, shrinkB=0))


# main pipeline (left -> right), 5 model stages + policy
xs = [2, 21, 40, 59, 78]
labels = ["CVAE\npopulation\nsynthesizer", "SILO\nland use", "ABIT\nactivity-based\ndemand",
          "MATSim\ndynamic\nassignment", "I-695\npricing\nscenario"]
cols = [STAGE, STAGE, STAGE, STAGE, POLICY]
W, H, Y = 16, 14, 26
for x, lab, c in zip(xs, labels, cols):
    box(x, Y, W, H, lab, c)
for i in range(len(xs) - 1):
    arrow(xs[i] + W, Y + H / 2, xs[i + 1], Y + H / 2)

# data inputs (top), feeding stages
inputs = [(2, "ACS / PUMS\nmicrodata"), (21, "Population\ncontrols"),
          (40, "Survey +\ncommute flows"), (59, "Network,\nspeeds, counts")]
for x, lab in inputs:
    box(x, 46, W, 8, lab, "white", tc=DATA, fs=7.0, ec=DATA)
    arrow(x + W / 2, 46, x + W / 2, Y + H)

# external-demand recovery notes (bottom)
box(30, 4, 24, 8, "Administrative-data\nworkplace assignment", "white", tc=EXT, fs=7.0, ec=EXT)
arrow(42, 12, 46, Y)  # into ABIT region
box(59, 4, 16, 8, "External-station\ngateway layer", "white", tc=EXT, fs=7.0, ec=EXT)
arrow(67, 12, 67, Y)

ps.save(fig, os.path.join(OUT, "platform_architecture"))
