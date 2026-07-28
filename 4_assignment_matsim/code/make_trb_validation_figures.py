#!/usr/bin/env python3
"""TRB publication-style validation figure suite for a MATSim linkstats dump.

Usage: python3 make_trb_validation_figures.py <linkstats.txt.gz> <out_dir> [<run_log>]

Outputs (600 dpi PNG + vector PDF, Okabe-Ito colorblind-safe palette):
  fig1_scatter_tiers      sim-vs-obs AADT scatter, 2x2 per facility tier, 1:1 +/-15% bands
  fig2_geh_cdf            cumulative GEH distribution by tier
  fig3_bias_distribution  distribution of log2(sim/obs) by tier
  fig4_tmas_hourly        hourly profile shape, model vs TMAS (freeway + arterial panels)
  fig5_cordon_gateways    boundary crossings: model vs observed vs resident-scope band
  fig6_convergence        stuck vehicles + average executed score by iteration
  fig7_nyc_benchmark      |rel diff| vs the He et al. NYC published standard
  metrics_by_tier.csv     full metric suite (n, bias, median/mean reldiff, GEH<5/<10, R2, corr2, %RMSE)
"""
import sys, os, gzip, re, ast
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
LS   = sys.argv[1]
OUT  = sys.argv[2]
LOG  = sys.argv[3] if len(sys.argv) > 3 else None
os.makedirs(OUT, exist_ok=True)
AADT = os.environ.get("AADT_FILE", f"{ROOT}/network_validation_2023/transitfix/aadt/aadt_validation_2023_qa.csv")  # QA-passed stations only
TMAS = f"{ROOT}/network_validation_2023/tmas/station_profiles.csv"
TMASV= f"{ROOT}/network_validation_2023/tmas/tmas_validation_2023.csv"
GWF  = f"{ROOT}/network_validation_2023/calibration/gateways_2023.csv"
SAMPLE = 10.0
TIERS = ["Interstate/Freeway","Principal Arterial","Minor Arterial","Collector/Local"]
# Okabe-Ito
COL = {"Interstate/Freeway":"#D55E00","Principal Arterial":"#E69F00",
       "Minor Arterial":"#009E73","Collector/Local":"#0072B2"}
# TRB publication style: serif (Times), 8-9 pt, black axes, no chartjunk, single-column sizing
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix", "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 7.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.linewidth": 0.8, "xtick.major.width": 0.8, "ytick.major.width": 0.8,
    "figure.dpi": 110})
def save(fig, name):
    fig.savefig(f"{OUT}/{name}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{OUT}/{name}.pdf", bbox_inches="tight")
    plt.close(fig); print(f"  saved {name}")

# ---------- load linkstats ----------
ls = pd.read_csv(LS, sep="\t", low_memory=False, dtype={"LINK":str})
ls["vol24"] = pd.to_numeric(ls["HRS0-24avg"], errors="coerce") * SAMPLE
vol = dict(zip(ls.LINK, ls.vol24))
hr_cols = [c for c in ls.columns if re.fullmatch(r"HRS(\d+)-(\d+)avg", c) and c != "HRS0-24avg"]
hr_cols = sorted(hr_cols, key=lambda c: int(re.match(r"HRS(\d+)-", c).group(1)))[:24]
HV = {}
if hr_cols:
    hm = ls[hr_cols].apply(pd.to_numeric, errors="coerce").values * SAMPLE
    HV = {k: hm[i] for i, k in enumerate(ls.LINK.values)}

# ---------- station matching (drop unmatched; same as v7 mainline analysis) ----------
df = pd.read_csv(AADT)
df = df[df.link_ids.notna() & (df.n_links > 0) & (df.obs_AADT > 0)].copy()
df["m"] = df.link_ids.apply(lambda s: sum(vol.get(l.strip(), 0.0) for l in str(s).split(";") if l.strip()))
df["geh"] = [np.sqrt(2*(m-o)**2/(m+o)) if (m+o) > 0 else np.nan for m, o in zip(df.m, df.obs_AADT)]
df["rd"] = (df.m - df.obs_AADT) / df.obs_AADT

# ---------- metrics table ----------
rows = []
for g in TIERS + ["ALL mainline"]:
    s = df[df.facility.isin(TIERS)] if g == "ALL mainline" else df[df.facility == g]
    m, o = s.m.values, s.obs_AADT.values
    sse = ((m-o)**2).sum(); sst = ((o-o.mean())**2).sum()
    rows.append(dict(facility=g, n=len(s), vol_ratio=m.sum()/o.sum(),
        mpe=float(100*s.rd.mean()),
        median_rel_diff=float(np.median(s.rd)), mean_abs_rel_diff=float(np.abs(s.rd).mean()),
        geh_lt5=100*(s.geh < 5).mean(), geh_lt10=100*(s.geh < 10).mean(),
        r2_true=1-sse/sst, corr2=np.corrcoef(m,o)[0,1]**2,
        pct_rmse=100*np.sqrt(((m-o)**2).mean())/o.mean()))
mt = pd.DataFrame(rows)
mt.to_csv(f"{OUT}/metrics_by_tier.csv", index=False)
print(mt.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

# ---------- fig1: 2x2 scatter with FHWA/NCHRP-255 per-facility deviation targets ----------
# Maximum desirable deviation in total link volume by facility class (FHWA Model Validation and
# Reasonableness Checking Manual / NCHRP 255 tradition): freeway +/-7%, principal +/-10%,
# minor +/-15%, collector +/-25%.
BAND = {"Interstate/Freeway": 0.07, "Principal Arterial": 0.10,
        "Minor Arterial": 0.15, "Collector/Local": 0.25}
SLUG = {"Interstate/Freeway": "freeway", "Principal Arterial": "principal",
        "Minor Arterial": "minor", "Collector/Local": "collector"}
lim = [0.2, 300]  # thousand veh/day
for g in TIERS:
    s = df[df.facility == g]; r = mt[mt.facility == g].iloc[0]
    b = BAND[g]
    fig, ax = plt.subplots(figsize=(3.5, 3.4))
    ax.plot(lim, lim, "k-", lw=0.8, zorder=1)
    ax.plot(lim, [(1+b)*l for l in lim], "k:", lw=0.9, zorder=1)
    ax.plot(lim, [(1-b)*l for l in lim], "k:", lw=0.9, zorder=1,
            label=f"±{int(100*b)}% FHWA/NCHRP-255 target")
    ax.scatter(s.obs_AADT/1e3, (s.m/1e3).clip(lower=lim[0]), s=8, c=COL[g], alpha=0.5, lw=0, zorder=2)
    inband = 100*float(((s.m >= (1-b)*s.obs_AADT) & (s.m <= (1+b)*s.obs_AADT)).mean())
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_title(g)
    ax.text(0.03, 0.97, f"n={r.n}\n$\\Sigma$sim/$\\Sigma$obs = {r.vol_ratio:.2f}\nwithin ±{int(100*b)}%: {inband:.0f}%",
            transform=ax.transAxes, va="top", fontsize=7.5)
    ax.legend(frameon=False, loc="lower right", fontsize=7)
    ax.set_xlabel("Observed AADT 2023 (thousand veh/day)")
    ax.set_ylabel("Simulated daily volume (thousand veh/day)")
    fmt = plt.FuncFormatter(lambda v, _: f"{v:g}")
    ax.xaxis.set_major_formatter(fmt); ax.yaxis.set_major_formatter(fmt)
    fig.tight_layout(); save(fig, f"fig1_{SLUG[g]}_scatter")

# ---------- fig8: ALL stations, one panel, +/-50% band ----------
fig, ax = plt.subplots(figsize=(5.0, 4.7))
ax.plot(lim, lim, "k-", lw=0.8, zorder=1)
ax.plot(lim, [1.5*l for l in lim], "k:", lw=0.9, zorder=1, label="±50% band")
ax.plot(lim, [0.5*l for l in lim], "k:", lw=0.9, zorder=1)
for g in TIERS:
    s = df[df.facility == g]
    ax.scatter(s.obs_AADT/1e3, (s.m/1e3).clip(lower=lim[0]), s=6, c=COL[g], alpha=0.4, lw=0, zorder=2, label=g)
sall = df[df.facility.isin(TIERS)]
in50 = 100*float(((sall.m >= 0.5*sall.obs_AADT) & (sall.m <= 1.5*sall.obs_AADT)).mean())
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
ax.set_xlabel("Observed AADT 2023 (thousand veh/day)"); ax.set_ylabel("Simulated daily volume (thousand veh/day)")
fmt = plt.FuncFormatter(lambda v, _: f"{v:g}")
ax.xaxis.set_major_formatter(fmt); ax.yaxis.set_major_formatter(fmt)
ax.text(0.03, 0.97, f"all mainline n={len(sall)}\nΣsim/Σobs={sall.m.sum()/sall.obs_AADT.sum():.2f}\nwithin ±50%: {in50:.0f}%\ncorr²={np.corrcoef(sall.m, sall.obs_AADT)[0,1]**2:.2f}",
        transform=ax.transAxes, va="top", fontsize=8, bbox=dict(fc="white", ec="0.8", alpha=0.9, pad=3))
ax.legend(fontsize=7, frameon=False, loc="lower right")
save(fig, "fig8_all_stations_50pct")

# ---------- fig9: I-695 station validation ----------
i695 = df[(df.get("ID_PREFIX") == "IS") & (df.get("ID_RTE_NO") == 695)].copy()
if len(i695):
    i695 = i695.sort_values("obs_AADT", ascending=False).reset_index(drop=True)
    fig, (axa, axb) = plt.subplots(1, 2, figsize=(8.6, 3.8), gridspec_kw={"width_ratios": [1.7, 1]})
    x = np.arange(len(i695)); w = 0.42
    axa.bar(x-w/2, i695.obs_AADT/1e3, w, color="0.72", label="Observed AADT 2023")
    axa.bar(x+w/2, i695.m/1e3, w, color="#D55E00", label="Simulated (×10)")
    axa.set_xticks(x[::4]); axa.set_xticklabels(i695.LOCATION_ID[::4], rotation=60, fontsize=6)
    axa.set_ylabel("Daily volume (thousands)"); axa.legend(fontsize=7, frameon=False)
    axa.set_title(f"I-695 Baltimore Beltway — {len(i695)} count stations", fontsize=9)
    l2 = [i695.obs_AADT.min()*0.6, i695.obs_AADT.max()*1.4]
    axb.plot(l2, l2, "k-", lw=0.8)
    axb.plot(l2, [1.5*l for l in l2], "k:", lw=0.9)
    axb.plot(l2, [0.5*l for l in l2], "k:", lw=0.9)
    axb.scatter(i695.obs_AADT/1e3*1e3, i695.m, s=16, c="#D55E00", alpha=0.7, lw=0)
    axb.set_xscale("log"); axb.set_yscale("log"); axb.set_xlim(l2); axb.set_ylim(l2)
    axb.set_xlabel("Observed AADT"); axb.set_ylabel("Simulated (×10)")
    rat = i695.m.sum()/i695.obs_AADT.sum()
    axb.set_title(f"Σsim/Σobs={rat:.2f}  median rel diff {100*np.median(i695.rd):.0f}%\n(resident-only scope: through+truck excluded)", fontsize=7.5)
    fig.tight_layout(); save(fig, "fig9_i695_stations")
    i695[["LOCATION_ID","obs_AADT","m","rd","geh"]].to_csv(f"{OUT}/i695_station_validation.csv", index=False)
else:
    print("  [fig9 skipped: no I-695 stations]")

# ---------- fig2: GEH CDF ----------
fig, ax = plt.subplots(figsize=(4.6, 3.4))
for g in TIERS:
    s = np.sort(df[df.facility == g].geh.dropna())
    ax.plot(s, 100*np.arange(1, len(s)+1)/len(s), color=COL[g], lw=1.6, label=g)
ax.axvline(5, color="0.4", ls=":", lw=0.8); ax.axvline(10, color="0.4", ls=":", lw=0.8)
ax.text(5, 101, "GEH 5", fontsize=7, ha="center"); ax.text(10, 101, "GEH 10", fontsize=7, ha="center")
ax.set_xlim(0, 40); ax.set_ylim(0, 100)
ax.set_xlabel("GEH statistic"); ax.set_ylabel("Cumulative share of stations (%)")
ax.legend(fontsize=7, frameon=False, loc="lower right")
save(fig, "fig2_geh_cdf")

# ---------- fig3: bias distribution ----------
fig, ax = plt.subplots(figsize=(4.6, 3.4))
data = [np.log2(df[df.facility == g].m.clip(lower=1) / df[df.facility == g].obs_AADT) for g in TIERS]
bp = ax.boxplot(data, tick_labels=[t.split("/")[0].split()[0] for t in TIERS], showfliers=False,
                patch_artist=True, medianprops=dict(color="black"))
for p, g in zip(bp["boxes"], TIERS): p.set_facecolor(COL[g]); p.set_alpha(0.6)
ax.axhline(0, color="k", lw=0.7)
ax.axhline(np.log2(1.15), color="0.5", ls="--", lw=0.6); ax.axhline(np.log2(0.85), color="0.5", ls="--", lw=0.6)
ax.set_ylabel("log$_2$(simulated / observed)"); ax.set_ylim(-3, 3)
save(fig, "fig3_bias_distribution")

# ---------- fig4: TMAS hourly shape ----------
try:
    tv = pd.read_csv(TMASV); tp = pd.read_csv(TMAS)
    tp = tp.merge(tv[["station_id", "fs", "link_ids"]], on="station_id", suffixes=("", "_v"))
    obs_c = [f"obs_h{h}" for h in range(24)]
    def prof(sub):
        o = sub[obs_c].sum().values
        m = np.zeros(24)
        for lids in sub.link_ids_v if "link_ids_v" in sub else sub.link_ids:
            for l in str(lids).split(";"):
                if l.strip() in HV: m += HV[l.strip()]
        return o/o.sum(), (m/m.sum() if m.sum() > 0 else m)
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 3.0), sharey=True)
    for ax, (name, sub) in zip(axs, [("Interstate (TMAS fs 1-2)", tp[tp.fs <= 2]),
                                     ("Arterial (TMAS fs 3+)", tp[tp.fs >= 3])]):
        o, m = prof(sub)
        ax.plot(range(24), 100*o, "k-", lw=1.6, label="Observed (TMAS 2023)")
        ax.plot(range(24), 100*m, color="#D55E00", lw=1.6, ls="--", label="Simulated")
        ax.set_title(name, fontsize=9); ax.set_xlabel("Hour of day"); ax.set_xticks(range(0, 24, 6))
    axs[0].set_ylabel("Share of daily volume (%)"); axs[0].legend(fontsize=7, frameon=False)
    fig.tight_layout(); save(fig, "fig4_tmas_hourly")
except Exception as e:
    print(f"  [fig4 skipped: {e}]")

# ---------- fig5: cordon gateways ----------
try:
    g18 = pd.read_csv(GWF)
    g18["model"] = g18.lids.apply(lambda s: sum(vol.get(str(l), 0.0) for l in ast.literal_eval(s)))
    g18["res_lo"] = (g18.cordon_aadt - g18.external - g18.truck_frac*g18.cordon_aadt).clip(lower=0)
    g18 = g18.sort_values("cordon_aadt", ascending=False).head(14)
    lbl = [r.road[:26] for _, r in g18.iterrows()]
    x = np.arange(len(g18)); w = 0.38
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    ax.bar(x-w/2, g18.cordon_aadt/1e3, w, color="0.75", label="Observed AADT (all vehicles)")
    ax.bar(x+w/2, g18.model/1e3, w, color="#0072B2", label="Simulated (resident scope, ×10)")
    ax.plot(x-w/2, g18.res_lo/1e3, "v", color="k", ms=4, label="Resident share (obs − through − truck)")
    ax.set_xticks(x); ax.set_xticklabels(lbl, rotation=40, ha="right", fontsize=6.5)
    ax.set_ylabel("Daily crossings (thousands)"); ax.legend(fontsize=7, frameon=False)
    fig.tight_layout(); save(fig, "fig5_cordon_gateways")
except Exception as e:
    print(f"  [fig5 skipped: {e}]")

# ---------- fig6: convergence ----------
try:
    outdir = os.path.dirname(os.path.dirname(os.path.dirname(LS)))
    sc = pd.read_csv(f"{outdir}/scorestats.csv", sep=None, engine="python")
    stuck = []
    if LOG and os.path.exists(LOG):
        for line in open(LOG, errors="ignore"):
            if "AT 36:00:00" in line and "QSim" in line:
                mm = re.search(r"lost=(\d+)", line)
                if mm: stuck.append(int(mm.group(1)))
    fig, ax1 = plt.subplots(figsize=(4.8, 3.2))
    it_col = [c for c in sc.columns if "ITER" in c.upper()][0]
    ex_col = [c for c in sc.columns if "executed" in c.lower()][0]
    ax1.plot(sc[it_col], sc[ex_col], color="#0072B2", lw=1.6, label="Avg executed plan score")
    ax1.set_xlabel("Iteration"); ax1.set_ylabel("Average executed score", color="#0072B2")
    if stuck:
        ax2 = ax1.twinx(); ax2.spines.right.set_visible(True)
        ax2.plot(range(len(stuck)), np.array(stuck)/1e3, color="#D55E00", lw=1.6, ls="--")
        ax2.set_ylabel("Stuck/aborted vehicles (thousands)", color="#D55E00"); ax2.set_ylim(bottom=0)
    fig.tight_layout(); save(fig, "fig6_convergence")
except Exception as e:
    print(f"  [fig6 skipped: {e}]")

# ---------- fig7: NYC benchmark ----------
fig, ax = plt.subplots(figsize=(4.6, 3.2))
ours_med = 100*np.abs(df[df.facility.isin(TIERS)].rd).median()
ours_avg = 100*np.abs(df[df.facility.isin(TIERS)].rd).mean()
maj = df[df.facility.isin(TIERS[:2])]
ax.bar([0, 1, 3, 4], [ours_med, ours_avg, 29, 39.8],
       color=["#0072B2", "#0072B2", "0.7", "0.7"], width=0.8)
ax.set_xticks([0, 1, 3, 4])
ax.set_xticklabels(["This model\nmedian", "This model\nmean", "NYC (He et al.)\nmedian", "NYC (He et al.)\nmean"], fontsize=7.5)
ax.set_ylabel("|Relative volume difference| (%)")
ax.text(0.5, -0.28, f"All mainline stations, n={len(df[df.facility.isin(TIERS)])}; major-network median: {100*np.abs(maj.rd).median():.0f}%",
        transform=ax.transAxes, ha="center", fontsize=7, color="0.35")
save(fig, "fig7_nyc_benchmark")

print(f"\nAll figures in {OUT}")
