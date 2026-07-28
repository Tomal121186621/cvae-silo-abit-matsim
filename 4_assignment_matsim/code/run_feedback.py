#!/usr/bin/env python3
"""Congested-skim FEEDBACK LOOP — the outer orchestrator that couples the tour-based demand model to
MATSim assignment until the zone-to-zone travel-time skims converge.

Each outer iteration k:
  1. apply demand  (tour model reads the CURRENT auto skim from the work dir) -> plans
  2. MATSim        (assign the plans on the network)                          -> events
  3. extract       (events -> realised congested zone-to-zone auto skim)
  4. MSA blend     skim_k = (1-1/k)*skim_{k-1} + (1/k)*new_k   (successive averages, stable)
  5. gap check     mean relative change of on-network OD times; stop when < TOL

Iteration 1 uses the base MITO free-flow skim; the loop then feeds congested times back so destination,
mode, and time-of-day respond to the realised network conditions — required for the I-695 pricing scenario.

Usage: python run_feedback.py [outer_iters] [matsim_inner_iters] [flowCap]
"""
import sys, os, shutil, subprocess
from pathlib import Path
import numpy as np, openmatrix as omx

MAT   = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
TBM   = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Tour Based MITO")
MITOSK= Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/ABIT/input/mito_los/skims")
APPLY = TBM/"code"/"apply"/"apply_plans.py"
APPLY_OUT = TBM/"code"/"apply"/"out"/"bmr_plans_tourbased.xml.gz"
JAR   = MAT/"code"/"matsim-run"/"target"/"baltimore-matsim-1.0.jar"
# HYBRID: speed-calibrated network + the toll-capable runner (RunBaltimoreToll, fixed modes) so a toll
# file drives route/departure-time; TBM_TOLL_FILE (default NONE) switches base vs pricing.
NET   = MAT/"scenarios/01_base_no_pricing/input/network/bmr_network_pt_speedcal.xml.gz"
TOLL  = os.environ.get("TBM_TOLL_FILE", "NONE")   # I-695 roadpricing xml, or NONE for the base loop
SCHED = MAT/"input/pt/schedule_mapped.xml.gz"
VEH   = MAT/"input/pt/transitVehicles.xml.gz"
WORK  = MAT/"runs"/"feedback"
SKDIR = WORK/"skims"                          # working skim dir the apply reads (TBM_SKIM_DIR)
JAVA  = subprocess.run(["/usr/libexec/java_home","-v","21"],capture_output=True,text=True).stdout.strip()

def sh(cmd, env=None, log=None):
    e=dict(os.environ); e.update(env or {})
    with open(log,"w") if log else subprocess.DEVNULL as f:
        r=subprocess.run(cmd, env=e, stdout=f if log else None, stderr=subprocess.STDOUT if log else None)
    if r.returncode!=0: raise RuntimeError(f"failed: {' '.join(map(str,cmd))}  (see {log})")

def read_omx(p):
    f=omx.open_file(str(p),"r"); M=np.array(f[f.list_matrices()[0]])
    zones=[int(z) for z in f.mapping(f.list_mappings()[0]).keys()]; f.close(); return M,zones

def write_omx(p, M, zones):
    if Path(p).exists(): Path(p).unlink()
    f=omx.open_file(str(p),"w"); f["mat1"]=M.astype(np.float32)
    f.create_mapping("origins",zones); f.create_mapping("destinations",zones); f.close()

# ---- OUTER-loop convergence instrumentation (car-share + skim + link-volume deltas per outer iter) ----
def car_share(plans_gz):
    import gzip
    car=tot=0
    with gzip.open(plans_gz,"rt") as f:
        for line in f:
            if "<leg " in line and 'mode="' in line:
                tot+=1
                if 'mode="car"' in line: car+=1
    return car/tot if tot else float("nan")

def panel_link_vol(rundir, inner, panel_links):
    """daily volume (x10) on the monitoring-panel links from this run's linkStats; None if unavailable."""
    import glob
    try:
        cand=glob.glob(str(rundir/"ITERS"/f"it.{inner}"/f"{inner}.linkstats.txt.gz")) \
             or glob.glob(str(rundir/"ITERS"/"**"/"*linkstats*"), recursive=True)
        if not cand: return None
        ls=pd.read_csv(sorted(cand)[-1], sep="\t", compression="gzip")
        lid=ls.columns[0]; vc=[c for c in ls.columns if "24" in str(c) and "avg" in str(c).lower()]
        if not vc: return None
        v=ls.set_index(lid)[vc[0]].astype(float)*10.0
        return np.array([float(v.get(str(l), v.get(l, 0.0))) for l in panel_links])
    except Exception as e:
        print(f"  [outer-log] panel volume read failed: {e}", flush=True); return None

def main():
    outer = int(sys.argv[1]) if len(sys.argv)>1 else 4
    inner = int(sys.argv[2]) if len(sys.argv)>2 else 6
    flow  = sys.argv[3] if len(sys.argv)>3 else "0.10"
    TOL   = 0.03
    SKDIR.mkdir(parents=True, exist_ok=True)
    # seed the work skim with the base MITO free-flow auto skim (iteration 1 input)
    shutil.copy(MITOSK/"traveltime_auto.omx", SKDIR/"traveltime_auto.omx")
    # CR-1 wiring guard: the toll-response mode choice is apply_plans.apply_mode's income-VOT MNL, which
    # applies a per-OD toll ($) iff SKDIR/toll_auto.omx exists. Base (TOLL=NONE) and pricing runs go
    # through that SAME income-VOT layer, so the toll must be the ONLY difference. Drop any stale toll skim
    # from a prior pricing run at seed time so a base loop never inherits a phantom toll.
    _stale_toll = SKDIR/"toll_auto.omx"
    if TOLL == "NONE" and _stale_toll.exists():
        _stale_toll.unlink(); print(f"  [seed] base loop: removed stale {_stale_toll.name}", flush=True)
    base,zones = read_omx(SKDIR/"traveltime_auto.omx")
    prev = base.copy()
    # outer-loop convergence log (mode-share <-> congested/tolled skim feedback), wired for the toll phase
    CONV = WORK/"outerloop_convergence.csv"
    with open(CONV,"w") as f:
        f.write("outer_iter,car_share,dcar_share_pp,skim_meanabs_min,skim_rmse_min,skim_relgap,linkvol_pct_rmse\n")
    try:
        _pl=pd.read_csv(MAT/"network_validation_2023/base_hybrid/monitoring_panel.csv")
        panel_links=sorted({x for s in _pl.link_ids.astype(str) for x in s.split(";") if x and x!="nan"})
    except Exception: panel_links=[]
    prev_carshare=None; prev_vol=None

    for k in range(1, outer+1):
        print(f"\n===== FEEDBACK ITERATION {k}/{outer} =====", flush=True)
        rundir = WORK/f"iter{k}"
        if k>1:                                                       # free disk: prior run's skim is already extracted
            old = WORK/f"iter{k-1}"
            if old.exists(): shutil.rmtree(old)
        # 1) demand (reads current congested skim from SKDIR); commute-shed 25mi, workplace-reassign on
        env=dict(TBM_SILO_YEAR="2023", TBM_SCOPE="mstm", TBM_CATCHMENT_MI="25",
                 TBM_REASSIGN_WORK="1", TBM_SKIM_DIR=str(SKDIR))
        print("  [1] demand ...", flush=True)
        sh(["python3", str(APPLY), "full", flow], env=env, log=WORK/f"apply_{k}.log")
        shutil.copy(APPLY_OUT, MAT/"input/population/bmr_plans_tourbased.xml.gz")
        # 2) MATSim + RoadPricing (RunBaltimoreToll, fixed modes = route+departure-time inner loop).
        #    storageCap 0.13 matches the validated base; plan.memory 3 fits the full pop in 13g.
        print(f"  [2] MATSim (toll={TOLL}) ...", flush=True)
        if rundir.exists(): shutil.rmtree(rundir)
        sh([f"{JAVA}/bin/java","-Xmx13g","-Dplan.memory=3","-cp",str(JAR),"de.umd.matsim.RunBaltimoreToll",
            str(NET), str(MAT/"input/population/bmr_plans_tourbased.xml.gz"), str(SCHED), str(VEH),
            str(rundir), str(inner), flow, "0.13", TOLL], log=WORK/f"matsim_{k}.log")
        # 3) extract congested TIME skim (feeds ABIT auto time); and, under a toll, the per-OD toll skim
        print("  [3] extract congested skim ...", flush=True)
        newsk = WORK/f"congested_{k}.omx"
        sh(["python3", str(MAT/"code"/"skim_from_events.py"),
            str(rundir/"output_events.xml.gz"), str(newsk), str(SKDIR/"traveltime_auto.omx")],
           log=WORK/f"skim_{k}.log")
        if TOLL != "NONE":
            print("  [3b] extract per-OD toll skim ...", flush=True)
            sh(["python3", str(MAT/"code"/"toll_from_events.py"),
                str(rundir/"output_events.xml.gz"), str(SKDIR/"toll_auto.omx")],
               log=WORK/f"toll_{k}.log")   # ABIT reads SKDIR/toll_auto.omx on the NEXT apply
        # free disk: drop the big interim plan dumps (keep events + histograms for inspection)
        import glob as _g
        for f in _g.glob(str(rundir/"ITERS"/"*"/"*.plans.xml.gz")): Path(f).unlink()
        new,_ = read_omx(newsk)
        # 4) MSA blend
        blended = (1.0-1.0/k)*prev + (1.0/k)*new
        # 5) gap (on-network cells that actually changed)
        chg = np.abs(new-prev); base_t = np.maximum(prev,1e-6)
        moved = new!=prev
        gap = float((chg[moved]/base_t[moved]).mean()) if moved.any() else 0.0
        # ---- outer-loop convergence metrics (vs previous outer iter) ----
        cs=car_share(MAT/"input/population/bmr_plans_tourbased.xml.gz")
        dcs=(cs-prev_carshare)*100 if prev_carshare is not None else float("nan")
        sk_mab=float(np.abs(new-prev)[moved].mean()) if moved.any() else 0.0
        sk_rmse=float(np.sqrt((np.square(new-prev)[moved]).mean())) if moved.any() else 0.0
        relgap=float(np.abs(new-prev).sum()/max(np.abs(new).sum(),1e-9))
        vol=panel_link_vol(rundir, inner, panel_links) if panel_links else None
        if vol is not None and prev_vol is not None and np.any(prev_vol>0):
            mk=prev_vol>0; lv=float(np.sqrt(np.mean(np.square((vol[mk]-prev_vol[mk])/prev_vol[mk])))*100)
        else: lv=float("nan")
        with open(CONV,"a") as f:
            f.write(f"{k},{cs:.4f},{dcs:.3f},{sk_mab:.4f},{sk_rmse:.4f},{relgap:.5f},{lv:.3f}\n")
        print(f"  [outer {k}] car_share={cs:.3f} dcar={dcs:+.2f}pp skim_rmse={sk_rmse:.3f}min "
              f"relgap={relgap:.4f} linkvol%rmse={lv:.2f}", flush=True)
        prev_carshare=cs; prev_vol=vol if vol is not None else prev_vol

        write_omx(SKDIR/"traveltime_auto.omx", blended, zones)
        prev = blended
        print(f"  gap (mean rel skim change) = {gap:.3f}   [tol {TOL}]", flush=True)
        if gap < TOL and k>=2:
            print(f"  CONVERGED at iteration {k}"); break
    print("\nfeedback loop done. Final plans + skims in", WORK)

if __name__=="__main__":
    main()
