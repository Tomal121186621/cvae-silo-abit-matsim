#!/usr/bin/env bash
# SubtourModeChoice ASC calibration v2 (2026-07-12) — retry on the FIXED base.
# Why retry: the original loop fought zone-centroid short-trip floors, gridlock and 20% demand excess —
# all since repaired; the runner also gained walk/bike max-distance cutoffs that cure the old floor.
# Setup: v14kb network (Key Bridge restored) + EXISTING MDTA tolls + v16-demand subsample (60k persons,
# directional-gateway build), SubtourModeChoice ON, 25 iterations/pass, ASC re-anchor between passes.
# Targets = the CURRENT validated demand's mode shares.
set -uo pipefail
cd "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim/scenarios/01_base_no_pricing"
ROOT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
JAVA="/Library/Java/JavaVirtualMachines/temurin-21-x64.jdk/Contents/Home/bin/java"
JAR="$ROOT/code/matsim-run/target/baltimore-matsim-1.0.jar"
NET="$ROOT/network_validation_2023/network_audit/bmr_network_pt_speedcal_capfix_v14kb.xml.gz"
POP="$ROOT/scenarios/01_base_no_pricing/input/pop_sub60k_v16demand.xml.gz"
TOLL="$ROOT/scenarios/01_base_no_pricing/input/roadpricing_existing_2023.xml"
SCHED="$ROOT/input/pt/schedule_mapped.xml.gz"; VEH="$ROOT/input/pt/transitVehicles.xml.gz"
PROG="calib_mc_v2.progress"
TARGETS="car=0.776,ride=0.1627,walk=0.0366,pt=0.018,bike=0.0068"   # current demand shares
CONV_CAR="2.0"; CONV_RIDE="1.5"; MAXPASS=6
# seed ASCs = the runner's defaults (last documented anchor point)
CAR=0.00; PT=-1.3150; RIDE=0.1261; WALK=1.4913; BIKE=-1.6355   # ref-corrected jump from pass-2 shares
# 60k persons of 298k (10% sample) -> 2.0% of region
FLOWCAP=0.0201; STORCAP=0.0800

log(){ echo "$(date '+%H:%M:%S') $*" | tee -a "$PROG"; }
: > "$PROG"

for PASS in $(seq 1 $MAXPASS); do
    OUT="output_calib_mc/pass${PASS}"
    rm -rf "$OUT"; mkdir -p output_calib_mc
    log "=== PASS $PASS | ASC car=$CAR pt=$PT ride=$RIDE walk=$WALK bike=$BIKE ==="
    "$JAVA" -Xmx8g -Dmodechoice=true \
        -Dasc.car=$CAR -Dasc.pt=$PT -Dasc.ride=$RIDE -Dasc.walk=$WALK -Dasc.bike=$BIKE \
        -cp "$JAR" de.umd.matsim.RunBaltimoreToll \
        "$NET" "$POP" "$SCHED" "$VEH" "$OUT" 25 $FLOWCAP $STORCAP "$TOLL" \
        > "output_calib_mc/pass${PASS}.log" 2>&1
    RC=$?
    [ $RC -ne 0 ] && { log "PASS $PASS FAILED rc=$RC"; exit 1; }
    RES=$(TARGETS="$TARGETS" AMP=1.0 CLAMP=4.0 python3 ../02_i695_congestion_pricing/reanchor_asc.py \
          "$OUT/modestats.csv" "$CAR" "$PT" "$RIDE" "$WALK" "$BIKE")
    echo "$RES" | grep -E '^#' | tee -a "$PROG"
    CARG=$(echo "$RES" | grep '^CAR_GAP_PP=' | cut -d= -f2)
    RIDEG=$(echo "$RES" | grep '^RIDE_GAP_PP=' | cut -d= -f2)
    read -r NCAR NPT NRIDE NWALK NBIKE < <(echo "$RES" | grep '^ASC_VALUES' | awk '{print $2,$3,$4,$5,$6}')
    cp "$OUT/modestats.csv" "output_calib_mc/pass${PASS}_modestats.csv"
    rm -rf "$OUT/ITERS"
    log "PASS $PASS done | car gap ${CARG}pp ride gap ${RIDEG}pp"
    if awk "BEGIN{exit !(${CARG} <= ${CONV_CAR} && ${RIDEG} <= ${CONV_RIDE})}"; then
        log "=== CONVERGED pass $PASS | FROZEN ASC car=$CAR pt=$PT ride=$RIDE walk=$WALK bike=$BIKE ==="
        echo "$CAR $PT $RIDE $WALK $BIKE" > output_calib_mc/FROZEN_ASCS.txt
        exit 0
    fi
    CAR=$NCAR; PT=$NPT; RIDE=$NRIDE; WALK=$NWALK; BIKE=$NBIKE
done
log "NOT converged in $MAXPASS passes"; exit 2
