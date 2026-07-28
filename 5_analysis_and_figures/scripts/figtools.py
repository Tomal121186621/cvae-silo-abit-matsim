"""Shared helpers for tiling pre-rendered panel images into one composite figure.

We tile existing 300-dpi PNG panels (each already fully labelled/titled) into a
single grid and export a vector PDF (raster panels embedded). Panel letters
(a), (b), ... are added top-left for in-text referencing.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
import string

TEXTWIDTH_IN = 6.5   # TRB single-column text width (letter, 1-in margins)


def _load(path, crop_frac=None):
    im = Image.open(path).convert("RGB")
    if crop_frac is not None:
        # keep the TOP crop_frac of the image (drops a lower panel/strip)
        w, h = im.size
        im = im.crop((0, 0, w, int(h * crop_frac)))
    return np.asarray(im)


def tile(paths, out_pdf, ncols, width_in=TEXTWIDTH_IN, panel_letters=True,
         crop_frac=None, letter_size=11, wspace=0.04, hspace=0.06,
         row_heights=None):
    """Tile `paths` into a grid with `ncols` columns; save vector PDF + PNG.

    crop_frac: if set, keep only the top fraction of every panel (used to drop
               SILO's redundant lower difference strip).
    row_heights: optional list of relative heights per row (for mixed layouts).
    """
    imgs = [_load(p, crop_frac) for p in paths]
    n = len(imgs)
    nrows = int(np.ceil(n / ncols))
    # per-cell aspect from the widest column set; use each image's own aspect
    aspects = [im.shape[0] / im.shape[1] for im in imgs]  # h/w
    cell_w = width_in / ncols
    # row height = max panel aspect in that row * cell width
    if row_heights is None:
        row_heights = []
        for r in range(nrows):
            row = aspects[r * ncols:(r + 1) * ncols]
            row_heights.append(max(row) * cell_w if row else 0)
    fig_h = sum(row_heights) * (1 + hspace)
    fig = plt.figure(figsize=(width_in, fig_h))
    gs = fig.add_gridspec(nrows, ncols, height_ratios=row_heights,
                          wspace=wspace, hspace=hspace)
    for i, im in enumerate(imgs):
        r, c = divmod(i, ncols)
        ax = fig.add_subplot(gs[r, c])
        ax.imshow(im)
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        if panel_letters:
            ax.text(0.01, 0.99, f"({string.ascii_lowercase[i]})",
                    transform=ax.transAxes, va="top", ha="left",
                    fontsize=letter_size, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white",
                              ec="none", alpha=0.75))
    # hide empty cells
    for i in range(n, nrows * ncols):
        r, c = divmod(i, ncols)
        ax = fig.add_subplot(gs[r, c]); ax.axis("off")
    fig.savefig(out_pdf, bbox_inches="tight", dpi=300)
    fig.savefig(out_pdf.replace(".pdf", ".png"), bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("wrote", out_pdf, f"({fig_h:.1f}in tall, {nrows}x{ncols})")
