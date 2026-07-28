#!/usr/bin/env bash
# I-695 congestion pricing — toll-capable runner (Phase 1: no-toll base with inner-loop mode choice).
#
# Same demand/network/qsim as the validated base but with SubtourModeChoice ON and the MD mode-choice
# model ported into the scorer (MODE_SCORER_MAPPING.md, walk/bike time-channel corrected). Mode ASCs are
# passed via -Dasc.* so the base can be re-anchored across calibration passes without recompiling.
#
# ASCs are calibrated on a SUBSAMPLE (fast, no plan-memory blowup), then frozen and applied to the full
# 280k population. Override PLANS / FLOWCAP / STORCAP / PLANMEM / XMX via environment for that:
#   PLANS=<sub.xml.gz> FLOWCAP=0.0178 STORCAP=0.0232 bash run_toll.sh <out> 50 NONE <ascs...>
#
# Usage: bash run_toll.sh <outDir> <iters> [tollFile|NONE] [ascCar ascPt ascRide ascWalk ascBike]
set -euo pipefail

MAT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
JAR="$MAT/code/matsim-run/target/baltimore-matsim-1.0.jar"
# speed-calibrated network (Tiwari/OSRM; travel-time MAPE 17.8%->3.8%). The toll response depends on
# realistic congested travel times, so the base ASC re-anchor AND all toll runs use this network.
NET="${NET:-$MAT/scenarios/01_base_no_pricing/input/network/bmr_network_pt_speedcal.xml.gz}"
SCHED="$MAT/input/pt/schedule_mapped.xml.gz"
VEH="$MAT/input/pt/transitVehicles.xml.gz"

# demand + qsim caps + memory (env-overridable for subsample calibration)
PLANS="${PLANS:-$MAT/scenarios/01_base_no_pricing/input/matsim_population_abit_bmr.xml.gz}"
FLOWCAP="${FLOWCAP:-0.10}"
STORCAP="${STORCAP:-0.13}"
PLANMEM="${PLANMEM:-5}"
XMX="${XMX:-13g}"
WRITE="${WRITE:-true}"   # false = disk-light calibration (modestats only); true = full outputs (final base)
THREADS="${THREADS:-8}"  # global + qsim threads (machine has 12 cores)

OUT="${1:?outDir required}"
ITER="${2:-64}"
TOLL="${3:-NONE}"

# ASCs (defaults = Sec.3 pre-anchor; override with args 4-8)
ASC_CAR="${4:-0.00}"
ASC_PT="${5:-2.25}"
ASC_RIDE="${6:-3.87}"
ASC_WALK="${7:-3.97}"
ASC_BIKE="${8:--0.20}"

export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
"$JAVA_HOME/bin/java" -Xmx"$XMX" \
    -Dasc.car="$ASC_CAR" -Dasc.pt="$ASC_PT" -Dasc.ride="$ASC_RIDE" \
    -Dasc.walk="$ASC_WALK" -Dasc.bike="$ASC_BIKE" -Dplan.memory="$PLANMEM" \
    -Dwrite.outputs="$WRITE" -Dthreads="$THREADS" \
    -cp "$JAR" de.umd.matsim.RunBaltimoreToll \
    "$NET" "$PLANS" "$SCHED" "$VEH" "$OUT" "$ITER" "$FLOWCAP" "$STORCAP" "$TOLL"
