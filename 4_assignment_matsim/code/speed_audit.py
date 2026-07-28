#!/usr/bin/env python3
"""Realized-speed audit of the base MATSim run (base_speedfix).

Question: beyond the fixed free-flow speeds, do vehicles EXPERIENCE realistic
realized speeds? -> freeways faster than arterials, congestion forming at peaks,
off-peak freeway back at facility standard (~65, not the broken-calibration 47).

Realized link speed(hour) = LENGTH / TRAVELTIME_avg(hour) * 2.23694 (mph),
read from ITERS/it.64/64.linkstats.txt.gz (hourly TRAVELTIME + volume columns).

Facility from osm:way:highway in output_network.xml.gz. Motorway (freeway, 65-mph
standard) and Trunk (expressway/tunnel, 50-mph standard) are kept SEPARATE -- pooling
them into one "Freeway" bar mixed a 65 and a 50 class under a single 65-mph reference
line, which contradicted its own 50-mph members (TRB review MJ-5). Classes:
  Motorway = motorway            (free-flow std 65)
  Trunk    = trunk               (free-flow std 50)
  Ramp     = motorway_link, trunk_link
  Primary  = primary (+_link)
  Secondary= secondary (+_link)
  Tertiary = tertiary (+_link)

NPMRDS 2023 raw observed speeds are NOT on disk (data/npmrds_2023 has only the
download README), so the reference is the facility free-flow standard. Section 4
(modeled-vs-observed) is emitted only if observed_speed_2023.csv appears later.

Outputs -> network_validation_2023/FINAL_FIGURES/speed_audit/
"""
import gzip, re, sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MS_TO_MPH = 2.2369362920544
ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
RUN  = ROOT/"scenarios/02_i695_congestion_pricing/output_base/base_speedfix"
NET  = RUN/"output_network.xml.gz"
LST  = RUN/"ITERS/it.64/64.linkstats.txt.gz"
OUT  = ROOT/"network_validation_2023/FINAL_FIGURES/speed_audit"
OUT.mkdir(parents=True, exist_ok=True)

# ---- TOD periods (hour = start hour of the HRSh-(h+1) column) -------------------
TOD = {
    "Free-flow (2-4AM)": [2, 3],
    "AM peak (7-9AM)":   [7, 8],
    "Midday (12-2PM)":   [12, 13],
    "PM peak (5-7PM)":   [17, 18],
}
TOD_ORDER = list(TOD)

FAC_ORDER = ["Motorway", "Trunk", "Primary", "Secondary", "Tertiary", "Ramp"]
FAC_STD = {"Motorway": 65, "Trunk": 50, "Primary": 40, "Secondary": 35, "Tertiary": 30, "Ramp": None}
FAC_COLOR = {"Motorway": "#1f4e79", "Trunk": "#0e8a8a", "Primary": "#2e7d32", "Secondary": "#e08a1e",
             "Tertiary": "#8e44ad", "Ramp": "#7f8c8d"}


def facility(hwy):
    if hwy == "motorway": return "Motorway"
    if hwy == "trunk": return "Trunk"
    if hwy in ("motorway_link", "trunk_link"): return "Ramp"
    if hwy in ("primary", "primary_link"): return "Primary"
    if hwy in ("secondary", "secondary_link"): return "Secondary"
    if hwy in ("tertiary", "tertiary_link"): return "Tertiary"
    return None


# ---- parse network: id -> (facility, name) -------------------------------------
_L = re.compile(r'<link id="([^"]+)"')
_H = re.compile(r'osm:way:highway" class="java.lang.String">([^<]+)<')
_N = re.compile(r'osm:way:name" class="java.lang.String">([^<]+)<')

def parse_net():
    print("[net] parsing", NET)
    fac = {}; name = {}
    cur = None; hwy = None; nm = None
    with gzip.open(NET, "rt") as f:
        for line in f:
            m = _L.search(line)
            if m:
                if cur is not None:
                    fc = facility(hwy)
                    if fc: fac[cur] = fc; name[cur] = nm or ""
                cur = m.group(1); hwy = None; nm = None
                continue
            if cur is not None:
                hm = _H.search(line)
                if hm: hwy = hm.group(1)
                nmm = _N.search(line)
                if nmm: nm = nmm.group(1)
        if cur is not None:
            fc = facility(hwy)
            if fc: fac[cur] = fc; name[cur] = nm or ""
    print(f"[net] {len(fac):,} freeway/primary/secondary/tertiary/ramp car links")
    return fac, name


# ---- read linkstats, compute realized speed per link per TOD -------------------
def read_linkstats(fac, name):
    print("[linkstats] reading", LST)
    df = pd.read_csv(LST, sep="\t")
    df["LINK"] = df["LINK"].astype(str)
    df = df[df["LINK"].isin(fac)].copy()
    df["facility"] = df["LINK"].map(fac)
    df["name"] = df["LINK"].map(name)
    L = df["LENGTH"].values

    # per-TOD volume-weighted space-mean realized speed per link
    for per, hrs in TOD.items():
        vol = np.zeros(len(df)); vsec = np.zeros(len(df)); freeflow_ok = np.zeros(len(df))
        for h in hrs:
            v = df[f"HRS{h}-{h+1}avg"].values
            tt = df[f"TRAVELTIME{h}-{h+1}avg"].values
            # per-hour realized speed; guard tt<=0
            vol += v
            vsec += v * tt
        # link speed across the period = sum(v*L) / sum(v*tt)  (VMT/VHT)
        with np.errstate(divide="ignore", invalid="ignore"):
            spd = np.where(vsec > 0, (vol * L) / vsec * MS_TO_MPH, np.nan)
        df[f"spd__{per}"] = spd
        df[f"vol__{per}"] = vol
    # free-flow POTENTIAL speed from freespeed (sanity anchor)
    df["freeflow_mph"] = df["FREESPEED"].values * MS_TO_MPH
    return df


def wmedian(vals, wts):
    vals = np.asarray(vals, float); wts = np.asarray(wts, float)
    m = np.isfinite(vals) & (wts > 0)
    vals, wts = vals[m], wts[m]
    if len(vals) == 0: return np.nan
    o = np.argsort(vals); vals, wts = vals[o], wts[o]
    c = np.cumsum(wts); cut = c[-1] / 2.0
    return vals[np.searchsorted(c, cut)]


# ---- aggregate facility x TOD --------------------------------------------------
def aggregate(df, minvol=1):
    rows = []
    for fc in FAC_ORDER:
        sub = df[df["facility"] == fc]
        rec = {"facility": fc, "n_links": len(sub)}
        for per in TOD_ORDER:
            s = sub[f"spd__{per}"].values
            v = sub[f"vol__{per}"].values
            m = np.isfinite(s) & (v >= minvol)
            rec[per] = np.median(s[m]) if m.sum() else np.nan
            rec[per + "__wmean"] = (np.nansum(s[m]*v[m])/v[m].sum()) if m.sum() else np.nan
            rec[per + "__nused"] = int(m.sum())
        rows.append(rec)
    return pd.DataFrame(rows).set_index("facility")


def corridor_table(df, minvol=1):
    corr = {
        "I-695 Baltimore Beltway": df["name"].str.contains("Baltimore Beltway", na=False),
        "I-95 (JFK Memorial Hwy)": df["name"].str.contains("John F. Kennedy Memorial", na=False),
        "I-83 Jones Falls Expwy":  df["name"].str.contains("Jones Falls Expressway", na=False),
        "I-83 Balt-Harrisburg":    df["name"].str.contains("Baltimore-Harrisburg Express", na=False),
        "Fort McHenry Tunnel":     df["name"].str.contains("Fort McHenry Tunnel", na=False),
        "Balt Harbor Tunnel":      df["name"].str.contains("Harbor Tunnel", na=False),
    }
    rows = []
    for lbl, mask in corr.items():
        sub = df[mask]
        rec = {"corridor": lbl, "n_links": len(sub),
               "ff_std_mph": round(sub["freeflow_mph"].median(), 1) if len(sub) else np.nan}
        for per in TOD_ORDER:
            s = sub[f"spd__{per}"].values; v = sub[f"vol__{per}"].values
            m = np.isfinite(s) & (v >= minvol)
            rec[per] = round(np.median(s[m]), 1) if m.sum() else np.nan
        rows.append(rec)
    return pd.DataFrame(rows).set_index("corridor")


# ================================ FIGURES =======================================
def fig_facility_tod(agg):
    fig, ax = plt.subplots(figsize=(9.6, 5.2))
    x = np.arange(len(TOD_ORDER)); w = 0.13; c0 = (len(FAC_ORDER) - 1) / 2.0
    for i, fc in enumerate(FAC_ORDER):
        vals = [agg.loc[fc, per] for per in TOD_ORDER]
        ax.bar(x + (i - c0) * w, vals, w, label=fc, color=FAC_COLOR[fc])
    # facility free-flow standard reference lines
    for fc, std in FAC_STD.items():
        if std: ax.axhline(std, ls=":", lw=0.8, color=FAC_COLOR[fc], alpha=0.6)
    # motorway (65) and trunk (50) standards drawn SEPARATELY (no longer pooled)
    ax.axhline(65, ls="--", lw=1.0, color="#1f4e79", alpha=0.9)
    ax.text(len(TOD_ORDER)-0.5, 65.6, "motorway free-flow std 65", fontsize=7.5,
            color="#1f4e79", ha="right")
    ax.axhline(50, ls="--", lw=1.0, color="#0e8a8a", alpha=0.9)
    ax.text(len(TOD_ORDER)-0.5, 50.6, "trunk free-flow std 50", fontsize=7.5,
            color="#0e8a8a", ha="right")
    ax.axhline(47, ls="--", lw=1.0, color="#c0392b", alpha=0.8)
    ax.text(len(TOD_ORDER)-0.5, 43.5, "broken-cal 47 (reverted)", fontsize=7.5,
            color="#c0392b", ha="right")
    ax.set_xticks(x); ax.set_xticklabels(TOD_ORDER, fontsize=9)
    ax.set_ylabel("Median realized (experienced) speed (mph)")
    ax.set_title("Realized speed by facility x time-of-day — base_speedfix (it.64)\n"
                 "vehicle-experienced speed on used links; motorway (65) and trunk (50) shown "
                 "separately (dotted = facility free-flow standard)",
                 fontsize=10.5)
    ax.legend(title="Facility", bbox_to_anchor=(1.01, 1), loc="upper left", frameon=False)
    ax.grid(True, axis="y", ls=":", lw=0.3, alpha=0.5)
    ax.set_ylim(0, 72)
    fig.tight_layout()
    fig.savefig(OUT/"1_realized_speed_by_facility_tod.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT/"1_realized_speed_by_facility_tod.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_advantage(agg):
    fig, ax = plt.subplots(figsize=(8.5, 5))
    x = np.arange(len(TOD_ORDER)); w = 0.35
    gap_p = [agg.loc["Motorway", per] - agg.loc["Primary", per] for per in TOD_ORDER]
    gap_a = [agg.loc["Motorway", per] -
             np.nanmean([agg.loc["Primary", per], agg.loc["Secondary", per],
                         agg.loc["Tertiary", per]]) for per in TOD_ORDER]
    ax.bar(x - w/2, gap_p, w, label="Motorway - Primary", color="#1f4e79")
    ax.bar(x + w/2, gap_a, w, label="Motorway - mean(arterial)", color="#5b9bd5")
    for i, (a, b) in enumerate(zip(gap_p, gap_a)):
        ax.text(i - w/2, a + 0.4, f"{a:.0f}", ha="center", fontsize=8)
        ax.text(i + w/2, b + 0.4, f"{b:.0f}", ha="center", fontsize=8)
    ax.axhline(0, color="k", lw=0.7)
    ax.set_xticks(x); ax.set_xticklabels(TOD_ORDER, fontsize=9)
    ax.set_ylabel("Speed advantage (mph)")
    ax.set_title("Motorway speed advantage over arterials by time-of-day\n"
                 "positive = motorways faster (trips rewarded for using freeways)",
                 fontsize=11)
    ax.legend(frameon=False, loc="upper left")
    ax.grid(True, axis="y", ls=":", lw=0.3, alpha=0.5)
    fig.tight_layout()
    fig.savefig(OUT/"2_freeway_speed_advantage.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT/"2_freeway_speed_advantage.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_corridors(ct):
    fig, ax = plt.subplots(figsize=(10, 5.4))
    corrs = ct.index.tolist()
    x = np.arange(len(corrs)); w = 0.2
    per_col = {"Free-flow (2-4AM)": "#95a5a6", "AM peak (7-9AM)": "#c0392b",
               "Midday (12-2PM)": "#27ae60", "PM peak (5-7PM)": "#8e44ad"}
    for i, per in enumerate(TOD_ORDER):
        vals = [ct.loc[c, per] for c in corrs]
        ax.bar(x + (i - 1.5) * w, vals, w, label=per, color=per_col[per])
    ax.axhline(65, ls="--", lw=0.9, color="#1f4e79", alpha=0.7)
    ax.text(len(corrs)-0.5, 66, "freeway std 65", fontsize=7.5, color="#1f4e79", ha="right")
    ax.axhline(50, ls="--", lw=0.9, color="#e67e22", alpha=0.7)
    ax.text(len(corrs)-0.5, 51, "tunnel std 50", fontsize=7.5, color="#e67e22", ha="right")
    ax.set_xticks(x); ax.set_xticklabels(corrs, fontsize=8, rotation=18, ha="right")
    ax.set_ylabel("Median realized speed (mph)")
    ax.set_title("Key corridor realized speeds by time-of-day — base_speedfix",
                 fontsize=11)
    ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    ax.grid(True, axis="y", ls=":", lw=0.3, alpha=0.5)
    ax.set_ylim(0, 72)
    fig.tight_layout()
    fig.savefig(OUT/"3_key_corridors_by_tod.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT/"3_key_corridors_by_tod.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_am_pm_corridor(ct):
    """AM vs PM realized speed for the beltway/freeway corridors (congestion check)."""
    fig, ax = plt.subplots(figsize=(9, 5))
    corrs = ct.index.tolist()
    x = np.arange(len(corrs)); w = 0.28
    ff = [ct.loc[c, "Free-flow (2-4AM)"] for c in corrs]
    am = [ct.loc[c, "AM peak (7-9AM)"] for c in corrs]
    pm = [ct.loc[c, "PM peak (5-7PM)"] for c in corrs]
    ax.bar(x - w, ff, w, label="Off-peak (2-4AM)", color="#95a5a6")
    ax.bar(x, am, w, label="AM peak", color="#c0392b")
    ax.bar(x + w, pm, w, label="PM peak", color="#8e44ad")
    ax.set_xticks(x); ax.set_xticklabels(corrs, fontsize=8, rotation=18, ha="right")
    ax.set_ylabel("Median realized speed (mph)")
    ax.set_title("Off-peak vs AM vs PM realized speed on key freeway corridors\n"
                 "(drop from off-peak = congestion forming)", fontsize=11)
    ax.legend(frameon=False, loc="lower right")
    ax.grid(True, axis="y", ls=":", lw=0.3, alpha=0.5)
    ax.set_ylim(0, 72)
    fig.tight_layout()
    fig.savefig(OUT/"4_corridor_am_pm_congestion.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT/"4_corridor_am_pm_congestion.pdf", bbox_inches="tight")
    plt.close(fig)


def congestion_diag(df, minvol=1):
    """Per facility x TOD: VMT-wtd mean, p15 speed, %VMT slower than 0.75*freespeed.

    The median hides localized bottlenecks; these VMT-weighted stats reveal whether
    any meaningful share of freeway travel is actually slowed at the peaks.
    """
    rows = []
    for fc in FAC_ORDER:
        sub = df[df["facility"] == fc]
        ff = sub["freeflow_mph"].values
        for per in TOD_ORDER:
            s = sub[f"spd__{per}"].values; v = sub[f"vol__{per}"].values
            m = np.isfinite(s) & (v >= minvol)
            sm, vm, ffm = s[m], v[m], ff[m]
            if len(sm) == 0:
                rows.append({"facility": fc, "period": per, "vmt_wmean": np.nan,
                             "p15": np.nan, "pct_vmt_congested": np.nan}); continue
            vmt = vm  # proxy weight (volume); length ~ similar, volume dominates
            wm = np.average(sm, weights=vmt)
            o = np.argsort(sm); c = np.cumsum(vmt[o]); p15 = sm[o][np.searchsorted(c, c[-1]*0.15)]
            cong = (sm < 0.75 * ffm)
            pct = 100 * vmt[cong].sum() / vmt.sum()
            rows.append({"facility": fc, "period": per, "vmt_wmean": round(wm, 1),
                         "p15": round(p15, 1), "pct_vmt_congested": round(pct, 1)})
    return pd.DataFrame(rows)


def fig_congestion(cd):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
    piv = cd.pivot(index="period", columns="facility", values="pct_vmt_congested").reindex(TOD_ORDER)[FAC_ORDER]
    x = np.arange(len(TOD_ORDER)); w = 0.13; c0 = (len(FAC_ORDER) - 1) / 2.0
    for i, fc in enumerate(FAC_ORDER):
        a1.bar(x + (i-c0)*w, piv[fc].values, w, label=fc, color=FAC_COLOR[fc])
    a1.set_xticks(x); a1.set_xticklabels(TOD_ORDER, fontsize=8, rotation=12)
    a1.set_ylabel("% of VMT slower than 0.75 x free-flow")
    a1.set_title("Share of travel that is congested, by facility x TOD", fontsize=10)
    a1.legend(frameon=False, fontsize=8); a1.grid(True, axis="y", ls=":", lw=0.3, alpha=0.5)

    pivp = cd.pivot(index="period", columns="facility", values="p15").reindex(TOD_ORDER)[FAC_ORDER]
    for i, fc in enumerate(FAC_ORDER):
        a2.bar(x + (i-c0)*w, pivp[fc].values, w, label=fc, color=FAC_COLOR[fc])
    a2.set_xticks(x); a2.set_xticklabels(TOD_ORDER, fontsize=8, rotation=12)
    a2.set_ylabel("15th-percentile realized speed (mph, VMT-wtd)")
    a2.set_title("Worst-15% (bottleneck) realized speed, by facility x TOD", fontsize=10)
    a2.grid(True, axis="y", ls=":", lw=0.3, alpha=0.5)
    fig.suptitle("Congestion diagnostics — does travel actually slow at the peaks? (base_speedfix)",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT/"5_congestion_diagnostics.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT/"5_congestion_diagnostics.pdf", bbox_inches="tight")
    plt.close(fig)


def main():
    fac, name = parse_net()
    df = read_linkstats(fac, name)
    agg = aggregate(df)
    ct = corridor_table(df)
    cd = congestion_diag(df)

    # save tables
    agg.round(2).to_csv(OUT/"realized_speed_by_facility_tod.csv")
    ct.to_csv(OUT/"key_corridor_speeds.csv")
    cd.to_csv(OUT/"congestion_diagnostics.csv", index=False)

    print("\n===== Realized speed by facility x TOD (median mph, used links) =====")
    print(agg[TOD_ORDER].round(1).to_string())
    print("\n===== Key corridors (median realized mph) =====")
    print(ct.to_string())

    fig_facility_tod(agg)
    fig_advantage(agg)
    fig_corridors(ct)
    fig_am_pm_corridor(ct)
    fig_congestion(cd)
    print("\n===== Congestion diagnostics (VMT-weighted) =====")
    print(cd.to_string(index=False))
    print("\n[figures] written to", OUT)

    # optional observed comparison if NPMRDS-derived table exists
    obs_p = ROOT/"network_validation_2023/speed/observed_speed_2023.csv"
    print(f"\n[obs] observed table present: {obs_p.exists()}")

if __name__ == "__main__":
    main()
