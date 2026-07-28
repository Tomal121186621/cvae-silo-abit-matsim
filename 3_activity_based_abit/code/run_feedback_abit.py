#!/usr/bin/env python3
"""ABIT <-> MATSim CONGESTED-SKIM FEEDBACK LOOP.

Adapted from Updated MATSim/code/run_feedback.py (the MSA orchestrator), swapping the DEMAND step from the
tour-based apply to ABIT (full-MSTM 10% -> BMR subarea cut -> study-area MATSim population).

Each outer iteration k:
  1. demand:  run ABIT reading the CURRENT (congested) car-time skim via `abit.skim.traveltime.file`,
              then build_studyarea.py -> output/matsim_population_abit_bmr.xml.gz
  2. assign:  MATSim (RunBaltimore) on that population -> output_events.xml.gz
  3. extract: skim_from_events.py -> realised congested zone-to-zone auto skim
  4. blend:   MSA  skim_{k} = (1-1/k)*skim_{k-1} + (1/k)*new_k   (successive averages)
  5. gap:     mean relative change of changed OD cells; stop when < TOL and k>=2

Iteration 1 reads the free-flow MITO skim; the loop feeds congested times back so ABIT's destination /
mode / time-of-day respond to realised conditions (required for the I-695 pricing scenario).

Toll: arg `toll` (default 0 = base). When >0 it is passed to ABIT's MarylandFullModeChoice.setToll (via
the auto.toll property) AND flagged for MATSim I-695 road-pricing (RunBaltimore road-pricing is a hook,
see note below). Base run = toll 0.

Usage: python run_feedback_abit.py [outer_iters=3] [matsim_inner=3] [sample_fraction=0.03] [toll=0]
"""
import sys, os, shutil, subprocess, glob
from pathlib import Path
import numpy as np, openmatrix as omx

ABIT  = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/ABIT")
MAT   = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim")
MITOSK= Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MITO/code/MITO_Inputs/skims")
PROPS_TMPL = ABIT/"input/maryland/maryland_full.properties"
BUILD = ABIT/"validation/build_studyarea.py"
ABIT_POP = ABIT/"output/matsim_population_abit_bmr.xml.gz"
JAR   = MAT/"code"/"matsim-run"/"target"/"baltimore-matsim-1.0.jar"
NET   = MAT/"input/network/bmr_network_pt.xml.gz"
SCHED = MAT/"input/pt/schedule_mapped.xml.gz"
VEH   = MAT/"input/pt/transitVehicles.xml.gz"
SKIM_EXTRACT = MAT/"code"/"skim_from_events.py"
WORK  = ABIT/"runs"/"feedback"
SKDIR = WORK/"skims"                     # working skim dir; ABIT reads SKDIR/traveltime_auto.omx
CP    = "target/classes:" + open("/tmp/abit_cp.txt").read().strip()
JAVA  = subprocess.run(["/usr/libexec/java_home","-v","21"],capture_output=True,text=True).stdout.strip()
NATIVE= "src/main/resources/lib/macosx64"

def sh(cmd, env=None, log=None, cwd=None):
    e=dict(os.environ); e.update(env or {})
    with (open(log,"w") if log else subprocess.DEVNULL) as f:
        r=subprocess.run(cmd, env=e, cwd=cwd, stdout=(f if log else None), stderr=(subprocess.STDOUT if log else None))
    if r.returncode!=0: raise RuntimeError(f"FAILED: {' '.join(map(str,cmd))}  (see {log})")

def read_omx(p):
    f=omx.open_file(str(p),"r"); M=np.array(f[f.list_matrices()[0]])
    zones=[int(z) for z in f.mapping(f.list_mappings()[0]).keys()]; f.close(); return M,zones

def write_omx(p, M, zones):
    if Path(p).exists(): Path(p).unlink()
    f=omx.open_file(str(p),"w"); f["mat1"]=M.astype(np.float32)
    f.create_mapping("origins",zones); f.create_mapping("destinations",zones); f.close()

def write_props(skim_path, toll, frac, threads=6):
    """ABIT properties for this iteration: point at the working (congested) skim + toll + sample."""
    txt = PROPS_TMPL.read_text()
    txt += f"\nabit.skim.traveltime.file = {skim_path}\n"
    txt += f"auto.toll = {toll}\n"
    txt += f"sample.fraction = {frac}\n"
    txt += f"number.of.threads = {threads}\n"
    p = WORK/"abit_iter.properties"; p.write_text(txt); return p

def main():
    outer = int(sys.argv[1]) if len(sys.argv)>1 else 3
    inner = int(sys.argv[2]) if len(sys.argv)>2 else 3
    frac  = float(sys.argv[3]) if len(sys.argv)>3 else 0.03
    toll  = float(sys.argv[4]) if len(sys.argv)>4 else 0.0
    flow  = f"{frac:.2f}"                 # MATSim flowCapFactor matches the ABIT sample
    TOL   = 0.03
    SKDIR.mkdir(parents=True, exist_ok=True)
    print(f"ABIT<->MATSim feedback: outer={outer} inner={inner} sample={frac} toll=${toll}", flush=True)
    if toll>0: print("  NOTE: toll passed to ABIT mode choice; MATSim I-695 road-pricing is a documented hook.", flush=True)

    # seed working skim with the free-flow MITO auto skim (iteration-1 input)
    shutil.copy(MITOSK/"traveltime_auto.omx", SKDIR/"traveltime_auto.omx")
    mito_ff,zones = read_omx(SKDIR/"traveltime_auto.omx")
    prev = mito_ff.copy()
    gaps=[]
    # network-consistent free-flow baseline (all car links at freespeed, same Dijkstra as skim_from_events)
    # -> the apples-to-apples reference to show congested times ROSE (vs the differently-sourced MITO skim)
    ffnet_path = WORK/"freeflow_network.omx"
    sh(["python3", str(ABIT/"code"/"freeflow_skim.py"), str(ffnet_path)], log=WORK/"freeflow.log")
    ffnet,_ = read_omx(ffnet_path)

    for k in range(1, outer+1):
        print(f"\n===== FEEDBACK ITERATION {k}/{outer} =====", flush=True)
        rundir = WORK/f"iter{k}"
        if k>1:                                                    # free disk: prior iter fully consumed
            old = WORK/f"iter{k-1}"
            if old.exists(): shutil.rmtree(old, ignore_errors=True)

        # ---- 1) DEMAND: ABIT reads the current congested skim ----
        print("  [1] ABIT demand (reads congested skim) ...", flush=True)
        props = write_props(SKDIR/"traveltime_auto.omx", toll, frac)
        sh([f"{JAVA}/bin/java","-Xmx14g",f"-Djava.library.path={NATIVE}","-cp",CP,
            "abm.RunAbitMarylandLos", str(props)], log=WORK/f"abit_{k}.log", cwd=str(ABIT))
        print("      subarea cut -> study-area MATSim population ...", flush=True)
        sh(["python3", str(BUILD)], log=WORK/f"build_{k}.log", cwd=str(ABIT))
        plans = WORK/f"pop_{k}.xml.gz"; shutil.copy(ABIT_POP, plans)

        # ---- 2) ASSIGN: MATSim ----
        print("  [2] MATSim assignment ...", flush=True)
        if rundir.exists(): shutil.rmtree(rundir)
        sh([f"{JAVA}/bin/java","-Xmx13g","-cp",str(JAR),"de.umd.matsim.RunBaltimore",
            str(NET), str(plans), str(SCHED), str(VEH), str(rundir), str(inner), flow, "0.5"],
           log=WORK/f"matsim_{k}.log")

        # ---- 3) EXTRACT congested skim ----
        print("  [3] extract congested skim ...", flush=True)
        newsk = WORK/f"congested_{k}.omx"
        sh(["python3", str(SKIM_EXTRACT), str(rundir/"output_events.xml.gz"), str(newsk),
            str(SKDIR/"traveltime_auto.omx")], log=WORK/f"skim_{k}.log")
        # free disk: drop big interim plan dumps (keep events + histograms)
        for f in glob.glob(str(rundir/"ITERS"/"*"/"*.plans.xml.gz")): Path(f).unlink()
        new,_ = read_omx(newsk)

        # ---- 4) MSA blend ----
        blended = (1.0-1.0/k)*prev + (1.0/k)*new

        # ---- 5) gap on changed cells ----
        moved = new!=prev
        gap = float((np.abs(new-prev)[moved]/np.maximum(prev,1e-6)[moved]).mean()) if moved.any() else 0.0
        gaps.append(gap)
        # congestion vs the NETWORK free-flow baseline (same network/method) on on-network cells
        cmask = (ffnet<180)&(ffnet>0)&(new<180)&(new>0)
        cong_mean = float(new[cmask].mean()); ff_mean = float(ffnet[cmask].mean())
        write_omx(SKDIR/"traveltime_auto.omx", blended, zones)
        prev = blended
        print(f"  gap (mean rel skim change) = {gap:.4f}   [tol {TOL}]", flush=True)
        print(f"  congested OD mean = {cong_mean:.2f} min vs free-flow {ff_mean:.2f} min "
              f"({'ROSE' if cong_mean>ff_mean else 'fell'} {(cong_mean-ff_mean)/max(ff_mean,1e-6)*100:+.1f}%)", flush=True)
        if gap < TOL and k>=2:
            print(f"  CONVERGED at iteration {k}", flush=True); break

    print(f"\n=== feedback done. gap trajectory: {[round(g,4) for g in gaps]} ===", flush=True)
    print(f"final congested skim + plans in {WORK}", flush=True)

if __name__=="__main__":
    main()
