#!/usr/bin/env python3
"""SPSA count calibration of the fully-loaded I-695 network (step 5).

Simultaneous Perturbation Stochastic Approximation (Spall 1992), MATSim-NYC recipe
(He, Chow & Ozbay, "A validated MATSim model for NYC", arXiv:2008.04762). Calibrates a small
parameter vector theta so simulated link volumes match observed 2023 AADT on the CALIBRATION
stations, then a single final full-population run produces the calibrated base network.

  theta = [ N_GW per-gateway through-inflow scale factors  s_g in [0.5, 2.0] ]  (N_GW = gateways w/ external>0)
          [ + optional 3 arterial capacity multipliers   c_f (principal/minor/collector) ]   <- off by default
  (freeway & ramp capacity FIXED; freeway loading is driven by the gateway through-seed, not capacity.)

Objective  f(theta) = facility-weighted %RMSE over the CALIBRATION stations:
    f = sqrt( SUM_s w(s) * ((sim_s - obs_s)/obs_s)^2  /  SUM_s w(s) )
  where sim_s = (sum of that station's matched-link 24h volumes) * (1/flowCap), obs_s = obs_AADT,
  and w(s) is a per-facility weight (freeways up-weighted). SUM(GEH) and corr2 are also logged.

SPSA iteration k (2 objective evaluations = 2 short MATSim runs per iteration):
    Delta_k        ~ Bernoulli(+/-1) per dimension
    theta_plus/minus = clamp(theta +/- c_k * Delta_k * step_scale)
    g_hat_k        = (f(theta_plus) - f(theta_minus)) / (2 * c_k * step_scale) * (1/Delta_k)
    theta          = clamp(theta - a_k * g_hat_k)
    a_k = a / (A + k + 1)^0.602      c_k = c / (k + 1)^0.101     (Spall's recommended exponents)

Runs on a SUBSAMPLE population with reduced inner iterations (disk-light, WRITE=false) for speed;
after ~10-20 SPSA iterations the best theta* is frozen and a FINAL FULL-POP run (WRITE=true, 64 iters)
writes the calibrated network + linkstats for out-of-sample validation (validate_holdout.py).

*** DESIGN + WIRING ONLY -- do NOT launch while the v8 base is assigning (shares the machine + jar). ***
Dry-run to inspect the plan without any MATSim:  python spsa_calibrate.py --dry-run
Real run (machine idle):                          bash scenarios/02_i695_congestion_pricing/run_spsa_calib.sh
"""
import argparse, glob, json, os, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
CODE = ROOT / "code"
CAL_STATIONS = ROOT / "network_validation_2023/calibration/spsa_calibration_stations.csv"
GATEWAYS = ROOT / "network_validation_2023/calibration/gateways_2023.csv"
NET_SPEEDFIX = ROOT / "network_validation_2023/network_audit/bmr_network_pt_speedcal_fixed.xml.gz"
RUN_TOLL = ROOT / "scenarios/02_i695_congestion_pricing/run_toll.sh"
WORK = ROOT / "runs" / "spsa"

# Number of gateway through-inflow scales = gateways with external>0 (dynamic; 14 -> 15 after I-83 added).
# MUST match seed_gateway_through_od.load_gateways(), which aligns --scales to the external>0 rows.
N_GW = int((pd.read_csv(GATEWAYS)["external"] > 0).sum())

# ---- calibration knobs (env-overridable via run_spsa_calib.sh) --------------------------------------
SPSA_POP    = os.environ.get("SPSA_POP", str(ROOT / "scenarios/02_i695_congestion_pricing/input/pop_sub50k.xml.gz"))
SPSA_FLOWCAP= float(os.environ.get("SPSA_FLOWCAP", "0.0178")) # qsim flowCap for the subsample
# Defect 4: the external/freight SEED sample MUST equal the count-scale fraction (1/SPSA_FLOWCAP), else
# agents seeded at one rate are scaled up by another -> ~1% systematic count bias. Tie sample to flowcap.
SPSA_SAMPLE = float(os.environ.get("SPSA_SAMPLE", str(SPSA_FLOWCAP)))
# Defect 3: it.0 gridlock removed ~29% of vehicles (removeStuckVehicles=true), depressing ALL link volumes.
# Give the subsample more storage headroom (storage >> flow) so queues hold instead of stucking out. ~2x flow.
SPSA_STORCAP= float(os.environ.get("SPSA_STORCAP", "0.0356"))
# Fraction of each gateway's external gap seeded as non-resident INFLOW/OUTFLOW (gateway<->interior zone,
# job/activity-attracted) vs pure THROUGH (gateway->gateway). Loads the radial freeway INTERIORS that
# through-only leaves starved. Cordon-conserving (through_frac = 1-inflow_frac). Calibrated to interior AADT.
SPSA_INFLOW_FRAC = float(os.environ.get("SPSA_INFLOW_FRAC", "0.5"))
SPSA_INNER  = int(os.environ.get("SPSA_INNER", "40"))         # MATSim inner iters per eval (reduced for speed)
SPSA_ITERS  = int(os.environ.get("SPSA_ITERS", "15"))         # SPSA iterations (2 MATSim runs each)
N_CAP_DIMS  = int(os.environ.get("SPSA_CAP_DIMS", "0"))       # 0 = gateway scales only; 3 = add arterial caps

# SPSA gain schedule (Spall)
A_GAIN = float(os.environ.get("SPSA_A", "0.50"))
C_GAIN = float(os.environ.get("SPSA_C", "0.10"))
A_STAB = max(1, int(0.10 * SPSA_ITERS))                        # stability constant ~10% of budget
GAMMA, ALPHA = 0.101, 0.602
# Finite-difference step: perturbation = ck*STEP_SCALE ~= 0.10 (+-10%) at k=1. The old 0.30 -> +-3% was
# below the MATSim mobsim noise floor, so [f+ - f-] was noise and theta would not move. A ~10% perturbation
# on gateway through-inflow produces a cordon-volume change that clears the noise. A_GAIN raised to 0.50 to
# match (theta step ~ a*ghat lands ~0.1/iter early). Both env-tunable (SPSA_A, SPSA_STEP).
STEP_SCALE = float(os.environ.get("SPSA_STEP", "1.0"))

GW_LO, GW_HI = 0.5, 2.0
CAP_FACS = ["principal", "minor", "collector"]
CAP_BOUNDS = {"principal": (0.47, 0.80), "minor": (0.80, 1.00), "collector": (0.83, 1.17)}
FAC_WEIGHT = {"Interstate/Freeway": 3.0, "Principal Arterial": 2.0, "Minor Arterial": 1.0, "Collector/Local": 1.0}

JAVA = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip()


# --------------------------------------------------------------------------- calibration targets
def load_targets():
    df = pd.read_csv(CAL_STATIONS)
    df["links"] = df["matched_link_ids"].astype(str).str.replace(";", ",").str.split(",")
    df["links"] = df["links"].apply(lambda ls: [x.strip() for x in ls if x.strip() and x.strip() != "nan"])
    df["w"] = df["facility"].map(FAC_WEIGHT).fillna(1.0)
    # OBSERVABILITY: theta = 15 gateway THROUGH-scales. Through-traffic enters/exits at the cordon and
    # traverses FREEWAYS; it barely touches interior arterials/collectors (those are driven by RESIDENT
    # demand, not gateways). Matching the ~460 arterial/collector sensors with gateway params is
    # unobservable -- it dilutes the gateway signal to ~8% of the objective and injects mobsim replanning
    # noise into the SPSA finite-difference, so theta random-walks near 1.0. Fix: CALIBRATE only on the
    # sensors theta controls = Interstate/Freeway screenline + the gateway cordon stations. Arterials go to
    # HELD-OUT validation (their residual is documented resident-scope). This is the MATSim-NYC structure
    # (calibrate to the sensors the demand affects). Set SPSA_CALIB_FACILITIES to override.
    AADT_FLOOR = float(os.environ.get("SPSA_AADT_FLOOR", "2000"))
    CALIB_FACS = os.environ.get("SPSA_CALIB_FACILITIES", "Interstate/Freeway").split("|")
    is_gw = df["is_gateway"] == 1 if "is_gateway" in df.columns else pd.Series(False, index=df.index)
    df = df[is_gw | (df["facility"].isin(CALIB_FACS) & (df["obs_AADT"] >= AADT_FLOOR))].copy()
    # REACHABILITY guard: a gateway whose through-demand is a negligible fraction of its cordon AADT cannot
    # be moved by its scale (e.g. I-70 Mt Airy: ramp-only, external 974 on a 55k mainline-AADT match ->
    # fixed -93% error). Drop such unreachable targets from the objective; flag in gateways_2023.csv for
    # link re-match. LOCATION_ID for gateways is "GW_<prefix>_<in_lid>".
    REACH_MIN = float(os.environ.get("SPSA_REACH_MIN", "0.05"))
    gw = pd.read_csv(GATEWAYS); gw = gw[gw["external"] > 0]
    reach = dict(zip(gw["in_lid"].astype(str), gw["external"] / gw["cordon_aadt"].clip(lower=1.0)))
    def _ok(r):
        if r["is_gateway"] != 1:
            return True
        return reach.get(str(r["LOCATION_ID"]).split("_")[-1], 1.0) >= REACH_MIN
    df = df[df.apply(_ok, axis=1)].reset_index(drop=True)
    return df


def read_linkvols(rundir, inner, scale):
    """{link_id: 24h volume * scale} from this run's it.<inner> linkstats (scale = 1/flowCap)."""
    cand = glob.glob(str(rundir / "ITERS" / f"it.{inner}" / f"{inner}.linkstats.txt.gz")) or \
           sorted(glob.glob(str(rundir / "ITERS" / "**" / "*linkstats*"), recursive=True))
    if not cand:
        raise FileNotFoundError(f"no linkstats under {rundir}")
    ls = pd.read_csv(sorted(cand)[-1], sep="\t", dtype={"LINK": str}, low_memory=False)
    # daily volume = the "HRS0-24avg" total. NOTE: a substring glob ("24"+"avg") also matches "HRS23-24avg"
    # (the 23:00-24:00 hour), which sorts first -> scoring on one near-empty late-night hour (~1% of AADT,
    # the -98.77% bias bug). Use the exact daily column, matching the proven netval2023_common validation.
    v = ls.set_index("LINK")["HRS0-24avg"].astype(float) * scale
    return v.to_dict()


def objective(vols, tgt):
    """facility-weighted %RMSE + diagnostics (GEH, corr2) over calibration stations."""
    sim, obs, w = [], [], []
    for _, r in tgt.iterrows():
        s = sum(vols.get(l, 0.0) for l in r["links"])
        sim.append(s); obs.append(r["obs_AADT"]); w.append(r["w"])
    sim = np.array(sim); obs = np.array(obs); w = np.array(w)
    ok = obs > 0
    rel = (sim[ok] - obs[ok]) / obs[ok]
    f = float(np.sqrt(np.sum(w[ok] * rel**2) / np.sum(w[ok])))
    geh = np.sqrt(2 * (sim[ok] - obs[ok])**2 / np.maximum(sim[ok] + obs[ok], 1e-9))
    corr2 = float(np.corrcoef(sim[ok], obs[ok])[0, 1]**2) if ok.sum() > 2 else float("nan")
    return f, {"wrmse_pct": 100 * f, "sumGEH": float(geh.sum()), "medGEH": float(np.median(geh)),
               "pctGEH5": float(100 * np.mean(geh < 5)), "corr2": corr2, "bias_pct": float(100 * np.mean(rel))}


# --------------------------------------------------------------------------- theta packing
def unpack(theta):
    gw = theta[:N_GW]
    cap = theta[N_GW:N_GW + N_CAP_DIMS] if N_CAP_DIMS else np.array([])
    return gw, cap


def clamp(theta):
    gw, cap = unpack(theta)
    gw = np.clip(gw, GW_LO, GW_HI)
    if N_CAP_DIMS:
        for i, fac in enumerate(CAP_FACS[:N_CAP_DIMS]):
            lo, hi = CAP_BOUNDS[fac]; cap[i] = np.clip(cap[i], lo, hi)
        return np.concatenate([gw, cap])
    return gw


# --------------------------------------------------------------------------- one objective evaluation
def sh(cmd, env=None, log=None):
    e = dict(os.environ); e.update(env or {})
    with (open(log, "w") if log else subprocess.DEVNULL) as f:
        r = subprocess.run(cmd, env=e, stdout=(f if log else None),
                           stderr=(subprocess.STDOUT if log else None))
    if r.returncode != 0:
        raise RuntimeError(f"failed: {' '.join(map(str, cmd))}  (see {log})")


def evaluate(theta, tag, tgt, dry_run=False):
    """Seed ext+freight with theta's gateway scales, (optionally) build a capacity net, run MATSim, score."""
    gw, cap = unpack(theta)
    WORK.mkdir(parents=True, exist_ok=True)
    scales_json = json.dumps(list(map(float, gw)))
    ext = WORK / f"plans_{tag}_ext.xml.gz"
    extfrt = WORK / f"plans_{tag}_extfrt.xml.gz"
    extfrtio = WORK / f"plans_{tag}_extfrtio.xml.gz"
    net = str(NET_SPEEDFIX)
    rundir = WORK / f"run_{tag}"

    if dry_run:
        print(f"  [dry] {tag}: gateway scales={np.round(gw,3).tolist()}"
              + (f" caps={np.round(cap,3).tolist()}" if N_CAP_DIMS else ""))
        return float("nan"), {}, {}

    # 1) external THROUGH-OD (sptime), reduced to through_frac = 1-inflow_frac of the gateway gap
    sh([sys.executable, str(CODE / "seed_gateway_through_od.py"), "--impedance", "sptime",
        "--scales", scales_json, "--through-frac", str(1.0 - SPSA_INFLOW_FRAC),
        "--base", SPSA_POP, "--out", str(ext), "--sample", str(SPSA_SAMPLE)],
       log=WORK / f"seed_ext_{tag}.log")
    # 2) freight PCE layer (same scales)
    sh([sys.executable, str(CODE / "seed_freight.py"), "--impedance", "sptime",
        "--scales", scales_json, "--base", str(ext), "--out", str(extfrt), "--sample", str(SPSA_SAMPLE)],
       log=WORK / f"seed_frt_{tag}.log")
    # 2b) non-resident INFLOW/OUTFLOW layer (gateway<->interior job/activity zones), inflow_frac of the gap.
    #     Loads the radial freeway interiors. Cordon marginal preserved (through_frac + inflow_frac = 1).
    sh([sys.executable, str(CODE / "seed_inflow_outflow.py"), "--impedance", "sptime",
        "--scales", scales_json, "--inflow-frac", str(SPSA_INFLOW_FRAC),
        "--base", str(extfrt), "--out", str(extfrtio), "--sample", str(SPSA_SAMPLE)],
       log=WORK / f"seed_io_{tag}.log")
    # 3) optional capacity net
    if N_CAP_DIMS:
        caps = {"freeway": 1.0, "ramp": 1.0}
        for i, fac in enumerate(CAP_FACS[:N_CAP_DIMS]):
            caps[fac] = float(cap[i])
        caps_json = WORK / f"caps_{tag}.json"; json.dump(caps, open(caps_json, "w"))
        net = str(WORK / f"net_{tag}.xml.gz")
        sh([sys.executable, str(CODE / "edit_network_capacity.py"), str(NET_SPEEDFIX), str(caps_json), net],
           log=WORK / f"caps_{tag}.log")
    # 4) MATSim. NOTE: WRITE=true is REQUIRED here -- SPSA scores on link volumes, and RunBaltimoreToll's
    #    disk-light branch (WRITE=false) sets writeLinkStatsInterval(0), i.e. NO linkstats => read_linkvols
    #    fails. With WRITE=true the jar writes linkStats every max(1,iters/8) iters averaged over the last
    #    <=5, so it.<inner>.linkstats.txt.gz exists (averaging even de-noises the mobsim). The extra
    #    events/plans dump is small on the 1.8% subsample and rundir is deleted right after scoring.
    if rundir.exists():
        shutil.rmtree(rundir)
    sh(["bash", str(RUN_TOLL), str(rundir), str(SPSA_INNER), "NONE"],
       env={"NET": net, "PLANS": str(extfrtio), "FLOWCAP": str(SPSA_FLOWCAP), "STORCAP": str(SPSA_STORCAP),
            "WRITE": "true", "THREADS": "8", "XMX": "13g", "PLANMEM": "5"},
       log=WORK / f"matsim_{tag}.log")
    # 5) score
    vols = read_linkvols(rundir, SPSA_INNER, 1.0 / SPSA_FLOWCAP)
    f, diag = objective(vols, tgt)
    shutil.rmtree(rundir, ignore_errors=True)     # free disk between evals
    for p in (ext, extfrt, extfrtio):
        p.unlink(missing_ok=True)
    return f, diag, vols


# --------------------------------------------------------------------------- warm-start (level fix)
def warmstart(tgt, passes):
    """Direct proportional cordon match to set the LEVEL before SPSA. SPSA's symmetric +-perturbation
    around theta=1 preserves the mean scale, so it is BLIND to the common-mode under-load (the dominant
    error, bias ~ -16%); it only sees the differential. So we first drive each gateway's cordon volume to
    its observed AADT by scaling ONLY the external (through) portion: theta_g <- theta_g * ext_target /
    (sim_g - cur_vol_g), where ext_target = external_g and cur_vol_g = resident crossings (both from
    gateways_2023.csv). A couple of MSA-style passes converge the 14 cordons; SPSA then refines the
    differential against the full freeway screenline (interior links that are NOT 1:1 with a gateway).
    This is standard SPSA practice -- initialise from a good prior, then refine (Spall)."""
    gwtab = pd.read_csv(GATEWAYS); gwtab = gwtab[gwtab["external"] > 0].reset_index(drop=True)
    lid2idx = {str(l): i for i, l in enumerate(gwtab["in_lid"])}
    cur = gwtab["cur_vol"].to_numpy(float); extval = gwtab["external"].to_numpy(float)
    gwt = tgt[tgt["is_gateway"] == 1].copy()
    theta = np.ones(N_GW)
    for p in range(passes):
        _, _, vols = evaluate(theta, f"ws{p}", tgt)
        for _, r in gwt.iterrows():
            i = lid2idx.get(str(r["LOCATION_ID"]).split("_")[-1])
            if i is None:
                continue
            sim = sum(vols.get(l, 0.0) for l in r["links"])
            ext_sim = sim - cur[i]                       # current through-portion at the cordon
            if ext_sim <= 0.05 * max(extval[i], 1.0):    # barely any through-volume -> push up hard
                theta[i] = min(theta[i] * 1.6, GW_HI)
            else:
                theta[i] = float(np.clip(theta[i] * extval[i] / ext_sim, GW_LO, GW_HI))
        json.dump(theta.tolist(), open(WORK / "theta_warmstart.json", "w"))
        print(f"warmstart pass {p+1}/{passes}: thetaMean={theta.mean():.3f} "
              f"spread={theta.max()-theta.min():.3f} [{theta.min():.2f}-{theta.max():.2f}]", flush=True)
    return clamp(theta)


# --------------------------------------------------------------------------- SPSA loop
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the plan/schedule, run NO MATSim")
    ap.add_argument("--resume", default=None, help="theta json to warm-start from")
    ap.add_argument("--warmstart", type=int, default=int(os.environ.get("SPSA_WARMSTART", "2")),
                    help="proportional cordon-match passes to set theta LEVEL before SPSA (0=skip)")
    args = ap.parse_args()

    tgt = load_targets()
    print(f"SPSA calibration: {len(tgt)} calibration stations "
          f"({int((tgt['is_gateway']==1).sum())} gateways)")
    print(f"  dims: {N_GW} gateway scales + {N_CAP_DIMS} capacity  |  iters={SPSA_ITERS} (2 runs each) + 1 final")
    print(f"  subsample pop={Path(SPSA_POP).name} sample={SPSA_SAMPLE} flowCap={SPSA_FLOWCAP} inner={SPSA_INNER}")
    print(f"  gains a={A_GAIN} c={C_GAIN} A={A_STAB} alpha={ALPHA} gamma={GAMMA}")

    ndim = N_GW + N_CAP_DIMS
    theta = np.ones(N_GW)
    if N_CAP_DIMS:
        theta = np.concatenate([theta, np.array([0.65, 0.90, 1.0][:N_CAP_DIMS])])
    if args.resume:
        theta = np.array(json.load(open(args.resume)), float)
        print(f"  resumed theta from {args.resume}")
    elif args.warmstart > 0 and not args.dry_run:
        print(f"  WARM-START: {args.warmstart} proportional cordon-match pass(es) to set theta level "
              f"(SPSA is blind to the common-mode; this fixes the ~-16% level first)")
        ws = warmstart(tgt, args.warmstart)
        theta = np.concatenate([ws, theta[N_GW:]]) if N_CAP_DIMS else ws
    theta = clamp(theta)
    print(f"  start theta: mean={theta[:N_GW].mean():.3f} spread={theta[:N_GW].max()-theta[:N_GW].min():.3f}")

    rng = np.random.default_rng(20230)
    WORK.mkdir(parents=True, exist_ok=True)
    hist = WORK / "spsa_history.csv"
    if not args.dry_run:
        with open(hist, "w") as h:
            h.write("iter,f_plus,f_minus,f_theta,wrmse_pct,sumGEH,pctGEH5,corr2,bias_pct,theta\n")

    best_f, best_theta = float("inf"), theta.copy()
    for k in range(SPSA_ITERS):
        ak = A_GAIN / (A_STAB + k + 1) ** ALPHA
        ck = C_GAIN / (k + 1) ** GAMMA
        delta = rng.choice([-1.0, 1.0], size=ndim)
        tp = clamp(theta + ck * delta * STEP_SCALE)
        tm = clamp(theta - ck * delta * STEP_SCALE)
        print(f"\n=== SPSA iter {k+1}/{SPSA_ITERS}  ak={ak:.4f} ck={ck:.4f} ===", flush=True)
        fp, _, _ = evaluate(tp, f"it{k}_p", tgt, args.dry_run)
        fm, _, _ = evaluate(tm, f"it{k}_m", tgt, args.dry_run)
        if args.dry_run:
            theta = clamp(theta - ak * (0.0))   # no-op; just walk the schedule
            continue
        ghat = (fp - fm) / (2.0 * ck * STEP_SCALE) * (1.0 / delta)
        theta = clamp(theta - ak * ghat)
        # evaluate the new incumbent for logging + best-tracking
        f0, diag, _ = evaluate(theta, f"it{k}_c", tgt, args.dry_run)
        with open(hist, "a") as h:
            h.write(f"{k+1},{fp:.5f},{fm:.5f},{f0:.5f},{diag['wrmse_pct']:.3f},{diag['sumGEH']:.1f},"
                    f"{diag['pctGEH5']:.1f},{diag['corr2']:.4f},{diag['bias_pct']:.2f},"
                    f"\"{np.round(theta,4).tolist()}\"\n")
        print(f"  f+={fp:.4f} f-={fm:.4f} f(theta)={f0:.4f}  wRMSE={diag['wrmse_pct']:.1f}% "
              f"%GEH<5={diag['pctGEH5']:.1f} corr2={diag['corr2']:.3f} bias={diag['bias_pct']:+.1f}%", flush=True)
        if f0 < best_f:
            best_f, best_theta = f0, theta.copy()
            json.dump(best_theta.tolist(), open(WORK / "theta_best.json", "w"))

    if args.dry_run:
        print("\n--dry-run complete (no MATSim launched). Schedule + wiring verified.")
        return

    json.dump(best_theta.tolist(), open(WORK / "theta_best.json", "w"))
    print(f"\nSPSA done. best f={best_f:.4f}  theta*-> {WORK/'theta_best.json'}")
    print("NEXT (manual, machine idle): build the calibrated base at full sample + write it, e.g.:")
    print(f"  python code/seed_gateway_through_od.py --impedance sptime --scales '{json.dumps(best_theta[:N_GW].tolist())}' \\")
    print(f"      --base scenarios/01_base_no_pricing/input/matsim_population_abit_bmr_v8.xml.gz \\")
    print(f"      --out input/population/bmr_plans_v8_external.xml.gz --sample 0.10")
    print(f"  python code/seed_freight.py --impedance sptime --scales '{json.dumps(best_theta[:N_GW].tolist())}' \\")
    print(f"      --base input/population/bmr_plans_v8_external.xml.gz \\")
    print(f"      --out input/population/bmr_plans_v8_loaded.xml.gz --sample 0.10")
    print("  # then RunBaltimoreToll on bmr_plans_v8_loaded.xml.gz at flowCap 0.10, 64 iters, WRITE=true")
    print("  # then: NETVAL_OUTDIR=<that run> python code/validate_holdout.py")


if __name__ == "__main__":
    main()
