"""Build CVAE composite figures for the TRB paper — re-plotted FROM DATA through the
shared paper_style so every panel is uniform in style, colour, size, and text.

Composites (figures/vae/):
  vae_hh_marginals   2x2 grouped bars (household marginals vs ACS-test)
  vae_pp_marginals   4x2 grouped bars (person marginals vs ACS-test)
  vae_cross          3x3 heatmaps (three bivariate pairs: ACS | VAE | difference)
  vae_association    1x3 Cramér's V matrices (ACS | VAE | difference)
  vae_overfit        1x2 line plots (train/val ELBO; reconstruction)  [panel c dropped]
"""
import os, sys, json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paper_style as ps
ps.apply()

VAE = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated VAE"
sys.path.insert(0, VAE)
OUT = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Paper Figures Final/figures/vae"
os.makedirs(OUT, exist_ok=True)
CACHE = os.path.join(HERE, ".cache_vae.npz")

LABELS = {
    "dwellingType": ["SFD", "SFA", "MF2-4", "MF5+", "MH"], "tenure": ["Own", "Rent"],
    "autos": ["0", "1", "2", "3", "4+"], "gender": ["Male", "Female"],
    "race": ["White", "Black", "Hisp.", "Asian", "Other"],
    "occupation": ["Emp.", "Student", "Retiree", "Unemp.", "Toddler", "Other"],
    "driversLicense": ["No", "Yes"], "nationality": ["Native", "Natur.", "Non-cit."],
    "relationship": ["Head", "Spouse", "Child", "Sibling", "Parent", "Other-r", "Non-rel", "GQ"],
}
AGE = [f"{5*i}-{5*i+4}" if i < 17 else "85+" for i in range(18)]
# income bin labels from vaelib config edges (outputs/00_raw_analysis/income_bin_edges.json)
# short lower-edge labels in $ thousands (axis title carries the "$k" unit)
HHINC = ["<0", "0", "10", "15", "20", "25", "30", "40", "50", "60", "75", "100",
         "125", "150", "175", "200", "250", "300", "400", "500", "750", "1M"]
PPINC = ["\u22640", "1", "10", "20", "30", "40", "50", "65", "80", "100", "125",
         "150", "200", "300", "500", "1M"]
TITLE = {"dwellingType": "Dwelling type", "tenure": "Tenure", "autos": "Vehicles",
         "hh_income_bin": "Household income bin", "age_bin": "Age band", "gender": "Gender",
         "race": "Race / ethnicity", "occupation": "Occupation", "driversLicense": "Driver's license",
         "relationship": "Relationship", "nationality": "Nationality", "pp_income_bin": "Person income bin"}
PAIRS = [("age_bin", "income_bin"), ("age_bin", "relationship"), ("occupation", "relationship")]


def compute():
    import torch
    from vaelib import config, crosswalks, validate as V
    from vaelib.model import CVAE, CVAEConfig
    from vaelib.zones import ZoneSampler
    from vaelib.generate import generate_population
    PRE = config.OUTPUTS_DIR / "01_preprocessed"; TGT = config.OUTPUTS_DIR / "02_targets"
    TR = config.OUTPUTS_DIR / "03_training" / "full"
    hh = pd.read_parquet(PRE / "hh.parquet").reset_index(drop=True)
    pp = pd.read_parquet(PRE / "pp.parquet")
    puma_to_idx = json.loads((TGT / "puma_to_idx.json").read_text())
    sp = np.load(TR / "split_idx.npz"); tr_idx, te_idx = sp["train"], sp["test"]
    train_hh, test_hh = hh.loc[tr_idx], hh.loc[te_idx]
    train_pp = pp[pp["SERIALNO"].isin(set(train_hh["SERIALNO"]))]
    test_pp = pp[pp["SERIALNO"].isin(set(test_hh["SERIALNO"]))]
    twh = test_hh["WGTP_eff"].to_numpy(); twp = test_pp["PWGTP_eff"].to_numpy()
    state = torch.load(TR / "checkpoint_best.pt", map_location="cpu", weights_only=False)
    model = CVAE(n_pumas=len(puma_to_idx), cfg=CVAEConfig(**state["model_cfg"]))
    model.load_state_dict(state["ema_state"]); model.eval()
    zsamp = ZoneSampler(crosswalks.build_zone_table(), rng=np.random.default_rng(7))
    print("generating 150k HH from train-only ...", flush=True)
    gen_hh, gen_pp = generate_population(model, train_hh, train_pp, puma_to_idx, zsamp,
                                         n_total=150000, seed=7, device="cpu")

    data = {}
    # marginals
    for lvl, vars_, ref, refw, gen in [
        ("hh", V.HH_VARS, test_hh, twh, gen_hh),
        ("pp", V.PP_VARS, test_pp, twp, gen_pp)]:
        gw = np.ones(len(gen))
        for name, n, base in vars_:
            p = V._dist(ref[name], refw, n, base); q = V._dist(gen[name], gw, n, base)
            data[f"m_{lvl}_{name}_obs"] = p; data[f"m_{lvl}_{name}_sim"] = q
            data[f"m_{lvl}_{name}_tv"] = np.array(V.tv(p, q))
    # bivariate joints (three pairs)
    ncp = {n: (c, b) for n, c, b in V.PP_VARS}
    for a, b in PAIRS:
        na, ba = ncp[a]; nb, bb = ncp[b]
        pa = (pd.to_numeric(test_pp[a]) - ba).clip(0, na - 1).to_numpy()
        pb = (pd.to_numeric(test_pp[b]) - bb).clip(0, nb - 1).to_numpy()
        T = np.histogram2d(pa, pb, bins=[na, nb], weights=twp)[0]; T = T / T.sum()
        ga = (pd.to_numeric(gen_pp[a]) - ba).clip(0, na - 1).to_numpy()
        gb = (pd.to_numeric(gen_pp[b]) - bb).clip(0, nb - 1).to_numpy()
        G = np.histogram2d(ga, gb, bins=[na, nb])[0]; G = G / G.sum()
        data[f"j_{a}_{b}_obs"] = T; data[f"j_{a}_{b}_sim"] = G
    # association: Cramér's V over the 8 person variables
    pv = [(n, c, b) for n, c, b in V.PP_VARS]
    names = [n for n, c, b in pv]
    K = len(pv)
    Vo = np.zeros((K, K)); Vs = np.zeros((K, K))
    def code(df, n, c, b):
        return (pd.to_numeric(df[n]) - b).clip(0, c - 1).to_numpy().astype(int)
    oc = {n: code(test_pp, n, c, b) for n, c, b in pv}
    sc = {n: code(gen_pp, n, c, b) for n, c, b in pv}
    nc = {n: c for n, c, b in pv}
    for i in range(K):
        for jj in range(K):
            ni, nj = names[i], names[jj]
            Vo[i, jj] = ps.cramers_v(oc[ni], oc[nj], nc[ni], nc[nj], twp)
            Vs[i, jj] = ps.cramers_v(sc[ni], sc[nj], nc[ni], nc[nj])
    data["assoc_obs"] = Vo; data["assoc_sim"] = Vs
    data["assoc_names"] = np.array(names)
    # training history
    h = pd.read_parquet(TR / "history.parquet")
    for c in ["epoch", "train_total", "val_total", "train_recon", "val_recon"]:
        data[f"h_{c}"] = h[c].to_numpy()
    np.savez(CACHE, **data)
    print("cached ->", CACHE)
    return data


def load():
    if os.path.exists(CACHE):
        d = np.load(CACHE, allow_pickle=True)
        return {k: d[k] for k in d.files}
    return compute()


D = load()

# ---------------- 1) household marginals (2x2) ----------------
def marg_fig(level, vars_, ncols, nrows, fname):
    fig, axs = plt.subplots(nrows, ncols, figsize=(ps.TEXTWIDTH_IN,
                            2.05 * nrows), squeeze=False)
    axs = axs.ravel()
    for i, name in enumerate(vars_):
        labkey = name
        labs = (AGE if name == "age_bin"
                else HHINC if (level == "hh" and name == "income_bin")
                else PPINC if (level == "pp" and name == "income_bin")
                else LABELS.get(name)
                or [str(t) for t in range(len(D[f"m_{level}_{name}_obs"]))])
        tk = "hh_income_bin" if (level == "hh" and name == "income_bin") else \
             ("pp_income_bin" if (level == "pp" and name == "income_bin") else name)
        tv = float(D[f"m_{level}_{name}_tv"])
        ps.grouped_bar(axs[i], labs,
                       [(ps.LAB_OBS, D[f"m_{level}_{name}_obs"] * 100, ps.OBS),
                        (ps.LAB_SIM, D[f"m_{level}_{name}_sim"] * 100, ps.SIM)],
                       title=f"{TITLE.get(tk, name)}  (TV={tv:.3f})",
                       sparse=8)
        ps.panel_letter(axs[i], i)
    h, l = axs[0].get_legend_handles_labels()
    ps.shared_legend(fig, h, l, ncol=2, y=1.005)
    fig.tight_layout(rect=[0, 0, 1, 0.975])
    ps.save(fig, os.path.join(OUT, fname))


SHORT = {"dwellingType": "Dwelling type", "tenure": "Tenure", "autos": "Vehicles",
         "hh_income_bin": "HH income (\\$k)", "age_bin": "Age band", "gender": "Gender",
         "race": "Race / eth.", "occupation": "Occupation", "driversLicense": "Driver lic.",
         "relationship": "Relationship", "nationality": "Nationality",
         "pp_income_bin": "Person income (\\$k)"}


def marg_combined(specs, ncols, fname):
    import math
    nrows = math.ceil(len(specs) / ncols)
    fig, axs = plt.subplots(nrows, ncols, figsize=(ps.TEXTWIDTH_IN, 1.32 * nrows), squeeze=False)
    axs = axs.ravel()
    for i, (level, name) in enumerate(specs):
        labs = (AGE if name == "age_bin"
                else HHINC if (level == "hh" and name == "income_bin")
                else PPINC if (level == "pp" and name == "income_bin")
                else LABELS.get(name)
                or [str(t) for t in range(len(D[f"m_{level}_{name}_obs"]))])
        tk = "hh_income_bin" if (level == "hh" and name == "income_bin") else \
             ("pp_income_bin" if (level == "pp" and name == "income_bin") else name)
        tv = float(D[f"m_{level}_{name}_tv"])
        # horizontal labels for short/few-category panels; diagonal only where needed;
        # only the long panels (income bins, age bands) are thinned, so no category is hidden.
        maxlen = max((len(str(l)) for l in labs), default=0)
        rot = 0 if (len(labs) <= 5 and maxlen <= 6) else 45
        sp = 6 if len(labs) > 12 else None
        ps.grouped_bar(axs[i], labs,
                       [(ps.LAB_OBS, D[f"m_{level}_{name}_obs"] * 100, ps.OBS),
                        (ps.LAB_SIM, D[f"m_{level}_{name}_sim"] * 100, ps.SIM)],
                       title=f"{SHORT.get(tk, name)} (TV={tv:.3f})", rotate=rot, sparse=sp)
        axs[i].tick_params(labelsize=6.5)
        ps.panel_letter(axs[i], i, size=7.5)
    for i in range(len(specs), nrows * ncols):
        axs[i].axis("off")
    h, l = axs[0].get_legend_handles_labels()
    ps.shared_legend(fig, h, l, ncol=2, y=1.002)
    fig.tight_layout(rect=[0, 0, 1, 0.975]); fig.subplots_adjust(hspace=0.95, wspace=0.33)
    ps.save(fig, os.path.join(OUT, fname))


marg_combined([("hh", "dwellingType"), ("hh", "tenure"), ("hh", "autos"), ("hh", "income_bin"),
               ("pp", "age_bin"), ("pp", "gender"), ("pp", "race"), ("pp", "occupation"),
               ("pp", "driversLicense"), ("pp", "relationship"), ("pp", "nationality"),
               ("pp", "income_bin")], 3, "vae_marginals")

# ---------------- 3) cross-relationships (3x3 heatmaps) ----------------
PNAME = {"age_bin": "Age band", "income_bin": "Income bin", "relationship": "Relationship",
         "occupation": "Occupation"}
fig, axs = plt.subplots(2, 3, figsize=(ps.TEXTWIDTH_IN, ps.TEXTWIDTH_IN * 0.66))
for r, (a, b) in enumerate(PAIRS[:2]):
    T = D[f"j_{a}_{b}_obs"]; G = D[f"j_{a}_{b}_sim"]
    vmax = max(T.max(), G.max()); dif = G - T; lim = np.abs(dif).max()
    ps.heatmap(axs[r, 0], T, vmin=0, vmax=vmax, ylabel=PNAME[b], cbar=True, fig=fig,
               title="Observed" if r == 0 else None)
    ps.heatmap(axs[r, 1], G, vmin=0, vmax=vmax, cbar=True, fig=fig,
               title="Model" if r == 0 else None)
    ps.heatmap(axs[r, 2], dif, cmap=ps.DIV_CMAP, vmin=-lim, vmax=lim, cbar=True, fig=fig,
               title="Difference" if r == 0 else None)
    # categorical tick labels: full names for short axes, sparse labeled ticks for long ones
    def _axticks(vals_name, n):
        if vals_name == "relationship":
            return list(range(n)), LABELS["relationship"][:n]
        if vals_name == "occupation":
            return list(range(n)), LABELS["occupation"][:n]
        if vals_name == "age_bin":
            tks = list(range(0, n, 4));  return tks, [AGE[t] for t in tks]
        if vals_name == "income_bin":
            tks = list(range(0, n, 4));  return tks, [PPINC[t] for t in tks]
        return None, None
    na, nb = D[f"j_{a}_{b}_obs"].shape
    xtk, xlb = _axticks(a, na); ytk, ylb = _axticks(b, nb)
    for c in range(3):
        axs[r, c].set_xlabel(PNAME[a])
        if xtk is not None:
            axs[r, c].set_xticks(xtk)
            axs[r, c].set_xticklabels(xlb, fontsize=5.5,
                rotation=45 if max(len(str(l)) for l in xlb) > 3 else 0,
                ha="right" if max(len(str(l)) for l in xlb) > 3 else "center")
        if ytk is not None:
            axs[r, c].set_yticks(ytk)
            axs[r, c].set_yticklabels(ylb if c == 0 else [""] * len(ylb), fontsize=5.5)
fig.tight_layout()
ps.save(fig, os.path.join(OUT, "vae_cross"))

# ---------------- 4) association: Cramér's V (1x3) ----------------
names = list(D["assoc_names"])
short = {"age_bin": "age", "gender": "sex", "race": "race", "occupation": "occ",
         "driversLicense": "lic", "relationship": "rel", "nationality": "nat",
         "income_bin": "inc"}
tk = [short.get(n, n) for n in names]
Vo, Vs = D["assoc_obs"], D["assoc_sim"]
fig, axs = plt.subplots(1, 3, figsize=(ps.TEXTWIDTH_IN, ps.TEXTWIDTH_IN * 0.40))
for ax, M, t, cm, lim in [(axs[0], Vo, "Observed", "viridis", None),
                          (axs[1], Vs, "Model", "viridis", None),
                          (axs[2], Vs - Vo, "Difference", ps.DIV_CMAP,
                           np.abs(Vs - Vo).max())]:
    vmin = 0 if lim is None else -lim
    vmax = max(Vo.max(), Vs.max()) if lim is None else lim
    im = ax.imshow(M, cmap=cm, vmin=vmin, vmax=vmax)
    ax.set_xticks(range(len(tk))); ax.set_xticklabels(tk, rotation=90, fontsize=7)
    ax.set_yticks(range(len(tk))); ax.set_yticklabels(tk, fontsize=7)
    ax.grid(False); ax.set_title(t)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
fig.tight_layout()
ps.save(fig, os.path.join(OUT, "vae_association"))

# ---------------- 5) overfitting: ELBO + reconstruction (1x2, no panel c) ----
ep = D["h_epoch"]
fig, axs = plt.subplots(1, 2, figsize=(ps.TEXTWIDTH_IN, ps.TEXTWIDTH_IN * 0.36))
axs[0].plot(ep, D["h_train_total"], color=ps.SIM, label="Train")
axs[0].plot(ep, D["h_val_total"], color=ps.OBS, label="Validation")
axs[0].set_xlabel("Epoch"); axs[0].set_ylabel("ELBO (recon + KL)")
axs[0].set_title("Training vs validation ELBO"); axs[0].legend()
ps.panel_letter(axs[0], 0)
axs[1].plot(ep, D["h_train_recon"], color=ps.SIM, label="Train")
axs[1].plot(ep, D["h_val_recon"], color=ps.OBS, label="Validation")
axs[1].set_xlabel("Epoch"); axs[1].set_ylabel("Reconstruction cross-entropy")
axs[1].set_title("Reconstruction loss"); axs[1].legend()
ps.panel_letter(axs[1], 1)
fig.tight_layout()
ps.save(fig, os.path.join(OUT, "vae_overfit"))

print("VAE composites done.")
