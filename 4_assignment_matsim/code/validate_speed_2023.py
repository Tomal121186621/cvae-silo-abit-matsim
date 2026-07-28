#!/usr/bin/env python3
"""NPMRDS 2023 speed validation — He, Chow, Ozbay et al. Sec 4.4 / Fig 15 equivalent.

Compares SIMULATED average speed vs OBSERVED NPMRDS speed by link type (Freeway /
Arterial) x 6 periods, reports the % difference (their targets: freeway ~7.2%,
arterial ~17.1%), and draws the grouped bar chart (their Fig 15).

Simulated speed of a link group in a period = total vehicle-metres / total
vehicle-seconds over all link traversals whose ENTER time falls in that period
(proper space-mean speed). Read from a MATSim events file.

Outputs (network_validation_2023/speed/):
  simulated_speed_2023.csv        type x period, mph
  speed_validation_2023.csv       obs, sim, %diff per type x period
And the figure (600 dpi PNG+PDF):
  network_validation_2023/figures_nyc_style/d_speed_by_period.{png,pdf}

Usage:
  python validate_speed_2023.py <events.xml.gz> [--net <network.xml.gz>] [--label TXT]
The <events> should be from the SPEED-CALIBRATED combined re-run; running it on the
pre-calibration base events yields a labelled 'pre-calibration' reference.
"""
import sys, gzip, re, argparse
from pathlib import Path
import numpy as np, pandas as pd

from speed_common import (ROOT, SPEED_OUT, MS_TO_MPH, PERIOD_ORDER, HOUR2PERIOD,
                          parse_car_links, group_key)

DEFAULT_NET = ROOT/"input/network/bmr_network_pt.xml.gz"
SPEED_OUT.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------- simulated speed from events
def simulated_speed(events_path, link_meta):
    """Return DataFrame [type x period] mph. link_meta: id -> (type, subcat, length)."""
    # accumulate vehicle-metres and vehicle-seconds per (type, period)
    dist = {}; time = {}
    ent = {}                      # (veh, link) -> enter time
    want = link_meta
    linkre = re.compile(r'link="([^"]+)"')
    vre    = re.compile(r'vehicle="([^"]+)"')
    tre    = re.compile(r'time="([0-9.]+)"')
    opn = gzip.open if str(events_path).endswith(".gz") else open
    with opn(events_path, "rt") as f:
        for line in f:
            isen = 'type="entered link"' in line
            islv = 'type="left link"' in line
            if not (isen or islv):
                continue
            lm = linkre.search(line)
            if not lm or lm.group(1) not in want:
                continue
            vm = vre.search(line); tm = tre.search(line)
            if not vm or not tm:
                continue
            lid = lm.group(1); veh = vm.group(1); t = float(tm.group(1))
            key = (veh, lid)
            if isen:
                ent[key] = t
            else:
                t0 = ent.pop(key, None)
                if t0 is None or t < t0:
                    continue
                typ, sub, length = want[lid]
                per = HOUR2PERIOD[int(t0 // 3600) % 24]
                gk = ("freeway" if typ == "freeway" else "arterial")
                dist[(gk, per)] = dist.get((gk, per), 0.0) + length
                time[(gk, per)] = time.get((gk, per), 0.0) + (t - t0)
    rows = {"freeway": {}, "arterial": {}}
    for (gk, per), d in dist.items():
        s = d / time[(gk, per)] if time[(gk, per)] > 0 else np.nan   # m/s
        rows[gk][per] = s * MS_TO_MPH
    tab = pd.DataFrame(rows).T.reindex(index=["freeway", "arterial"], columns=PERIOD_ORDER)
    return tab


# --------------------------------------------------- figure (paper Fig 15)
def make_figure(obs, sim, label, out_dir):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix", "font.size": 10, "axes.titlesize": 11,
        "axes.labelsize": 10, "legend.fontsize": 8, "xtick.labelsize": 9,
        "ytick.labelsize": 9, "axes.linewidth": 0.7, "savefig.dpi": 600, "figure.dpi": 120})
    x = np.arange(len(PERIOD_ORDER)); w = 0.2
    C = {"fwy_obs": "#2E5C8A", "fwy_sim": "#D46A1E",
         "art_obs": "#8FA9C6", "art_sim": "#E7B48A"}
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    fwy_o = obs.loc["freeway", PERIOD_ORDER].values.astype(float)
    fwy_s = sim.loc["freeway", PERIOD_ORDER].values.astype(float)
    art_o = obs.loc["arterial", PERIOD_ORDER].values.astype(float)
    art_s = sim.loc["arterial", PERIOD_ORDER].values.astype(float)
    ax.bar(x-1.5*w, fwy_o, w, color=C["fwy_obs"], label="Freeway NPMRDS (obs)")
    ax.bar(x-0.5*w, fwy_s, w, color=C["fwy_sim"], label="Freeway simulated")
    ax.bar(x+0.5*w, art_o, w, color=C["art_obs"], label="Arterial NPMRDS (obs)")
    ax.bar(x+1.5*w, art_s, w, color=C["art_sim"], label="Arterial simulated")
    ax.set_xticks(x); ax.set_xticklabels(PERIOD_ORDER, fontsize=8.5)
    ax.set_ylabel("Average speed (mph)"); ax.set_xlabel("Time period")
    fwy_d = np.nanmean(np.abs(fwy_s-fwy_o)/fwy_o)*100
    art_d = np.nanmean(np.abs(art_s-art_o)/art_o)*100
    ax.set_title(f"NPMRDS (observed) vs simulated speed by period — {label}\n"
                 f"freeway avg |diff| {fwy_d:.1f}%  ·  arterial avg |diff| {art_d:.1f}%")
    ax.legend(frameon=True, loc="upper left", ncol=2)
    ax.grid(True, axis="y", ls=":", lw=0.3, alpha=0.5)
    ax.text(0.99, 0.02, "NYC ref (He et al. Fig 15): freeway 7.2% · arterial 17.1%",
            transform=ax.transAxes, va="bottom", ha="right", fontsize=7.5,
            style="italic", color="#555")
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir/"d_speed_by_period.png", bbox_inches="tight")
    fig.savefig(out_dir/"d_speed_by_period.pdf", bbox_inches="tight")
    plt.close(fig)
    return fwy_d, art_d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("events")
    ap.add_argument("--net", default=None)
    ap.add_argument("--label", default="2023")
    args = ap.parse_args()
    net = Path(args.net) if args.net else DEFAULT_NET

    print(f"[net] {net}")
    link_meta = {}
    for l in parse_car_links(net):
        if l["type"] is not None:
            link_meta[l["id"]] = (l["type"], l["subcat"], l["length"])
    print(f"[net] {len(link_meta):,} freeway+arterial car links tracked")

    print(f"[events] {args.events}  (single streaming pass)")
    sim = simulated_speed(args.events, link_meta)
    sim.round(3).to_csv(SPEED_OUT/"simulated_speed_2023.csv")
    print("[sim] simulated mean speed (mph):"); print(sim.round(2).to_string())
    print(f"[write] {SPEED_OUT/'simulated_speed_2023.csv'}")

    obs_path = SPEED_OUT/"observed_speed_2023.csv"
    if not obs_path.exists():
        print("\n[obs] observed_speed_2023.csv not present — run calibrate_speed_2023.py "
              "on the NPMRDS export first. Simulated table written; figure deferred.")
        return 2
    obs = pd.read_csv(obs_path, index_col=0).reindex(index=["freeway", "arterial"],
                                                     columns=PERIOD_ORDER)
    # comparison table
    rows = []
    for typ in ["freeway", "arterial"]:
        for per in PERIOD_ORDER:
            o = obs.loc[typ, per]; s = sim.loc[typ, per]
            rows.append({"type": typ, "period": per, "obs_mph": round(o, 2),
                         "sim_mph": round(s, 2),
                         "diff_pct": round((s-o)/o*100, 1) if o else np.nan})
    comp = pd.DataFrame(rows)
    comp.to_csv(SPEED_OUT/"speed_validation_2023.csv", index=False)
    print(f"[write] {SPEED_OUT/'speed_validation_2023.csv'}")

    fwy_d, art_d = make_figure(obs, sim, args.label,
                               ROOT/"network_validation_2023/figures_nyc_style")
    print(f"\n[result] freeway avg |diff| {fwy_d:.1f}%  (NYC 7.2%) ; "
          f"arterial avg |diff| {art_d:.1f}%  (NYC 17.1%)")
    print(f"[write] figures_nyc_style/d_speed_by_period.png/.pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
