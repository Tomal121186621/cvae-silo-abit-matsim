"""Single shared figure style for the whole TRB paper.

Every composite figure in the paper is plotted from data through THIS module so that
fonts, colours, sizes, legends, and panel letters are identical across CVAE, SILO,
ABIT, and MATSim exhibits. No captions are baked into images — captions live in LaTeX.

Convention (colour-blind safe, Wong palette):
  OBSERVED (ACS / RTS / AADT / census truth)  -> orange   #D55E00
  MODEL    (VAE / SILO / ABIT / MATSim)        -> blue     #0072B2
  TARGET   (benchmark / control total)         -> green    #009E73
  NEUTRAL  (references, gridlines)             -> gray     #4D4D4D
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import string

OBS = "#D55E00"      # observed / ground truth
SIM = "#0072B2"      # model output
TARGET = "#009E73"   # benchmark / target
NEUTRAL = "#4D4D4D"
ACCENT = "#CC79A7"
SEQ_CMAP = "cividis"
DIV_CMAP = "RdBu_r"

TEXTWIDTH_IN = 6.5   # TRB single-column text width (letter, 1-in margins)

# canonical legend labels reused across the paper
LAB_OBS = "Observed"
LAB_SIM = "Model"


def apply():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "axes.linewidth": 0.8,
        "axes.edgecolor": "#333333",
        "axes.grid": True,
        "grid.color": "#DDDDDD",
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "lines.linewidth": 1.3,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "legend.frameon": False,
        "pdf.fonttype": 42,   # embed TrueType (editable text in vector PDF)
        "ps.fonttype": 42,
    })


def panel_letter(ax, i, size=9.5):
    """Prefix the panel letter to the panel title as a single left-aligned title
    OUTSIDE the plot area, so it never overlaps the data or the title text."""
    t = ax.get_title().strip()
    ax.set_title("")  # clear the centered title
    lab = f"({string.ascii_lowercase[i]})"
    ax.set_title(f"{lab} {t}".strip(), loc="left", fontsize=size, fontweight="bold")


def grouped_bar(ax, labels, series, title=None, ylabel="Share (%)",
                rotate=None, sparse=None):
    """series = list of (label, values, colour). Uniform grouped-bar panel."""
    n = len(labels)
    x = np.arange(n)
    k = len(series)
    w = 0.8 / k
    for j, (lab, vals, col) in enumerate(series):
        ax.bar(x + (j - (k - 1) / 2) * w, np.asarray(vals), w, color=col, label=lab)
    ax.set_xticks(x)
    if sparse and n > sparse:
        show = [labels[t] if t % 2 == 0 else "" for t in range(n)]
    else:
        show = labels
    if rotate is None:
        rotate = 45 if max((len(str(s)) for s in labels), default=0) > 3 else 0
    ax.set_xticklabels(show, rotation=rotate, ha="right" if rotate else "center")
    ax.set_ylabel(ylabel)
    ax.margins(x=0.02)
    if title:
        ax.set_title(title)


def heatmap(ax, M, cmap=SEQ_CMAP, vmin=None, vmax=None, title=None,
            xlabel=None, ylabel=None, cbar=True, fig=None):
    im = ax.imshow(np.asarray(M).T, origin="lower", aspect="auto",
                   cmap=cmap, vmin=vmin, vmax=vmax)
    ax.grid(False)
    if title:
        ax.set_title(title)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if cbar and fig is not None:
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    return im


def shared_legend(fig, handles, labels, ncol=2, y=1.0):
    fig.legend(handles, labels, loc="upper center", ncol=ncol,
               bbox_to_anchor=(0.5, y), frameon=False)


def save(fig, path_no_ext):
    fig.savefig(path_no_ext + ".pdf", bbox_inches="tight")
    fig.savefig(path_no_ext + ".png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("wrote", path_no_ext + ".pdf")


def cramers_v(a, b, na, nb, w=None):
    """Bias-corrected Cramér's V between two integer-coded categoricals."""
    a = np.asarray(a); b = np.asarray(b)
    if w is None:
        w = np.ones(len(a))
    T = np.histogram2d(a, b, bins=[na, nb], range=[[0, na], [0, nb]], weights=w)[0]
    Ntot = T.sum()
    if Ntot <= 0:
        return 0.0
    row = T.sum(1, keepdims=True); col = T.sum(0, keepdims=True)
    E = row @ col / Ntot
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = np.nansum(np.where(E > 0, (T - E) ** 2 / E, 0.0))
    phi2 = chi2 / Ntot
    r, k = na, nb
    phi2c = max(0.0, phi2 - (k - 1) * (r - 1) / (Ntot - 1))
    rc = r - (r - 1) ** 2 / (Ntot - 1)
    kc = k - (k - 1) ** 2 / (Ntot - 1)
    denom = min(kc - 1, rc - 1)
    return float(np.sqrt(phi2c / denom)) if denom > 0 else 0.0
