#!/usr/bin/env bash
# SubtourModeChoice ASC calibration v3: WARM-START passes (each pass continues from the previous
# pass's evolved output_plans instead of resetting to input plans) so mode-choice mixing COMPOUNDS.
# v2 diagnosis: shares responded to ASC but each 25-it pass restarted cold -> equilibrium never
# accumulated (car stuck ~68%). Ref-corrected re-anchor formula retained.
set -uo pipefail
cd "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim/scenarios/01_base_no_pricing"
ROOT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
JAVA="/Library/Java/JavaVirtualMachines/temurin-21-x64.jdk/Contents/Home/bin/java"
JAR="$ROOT/code/matsim-run/target/baltimore-matsim-1.0.jar"
NET="$ROOT/network_validation_2023/network_audit/bmr_network_pt_speedcal_capfix_v14kb.xml.gz"
TOLL="$ROOT/scenarios/01_base_no_pricing/input/roadpricing_existing_2023.xml"
SCHED="$ROOT/input/pt/schedule_mapped.xml.gz"; VEH="$ROOT/input/pt/transitVehicles.xml.gz"
PROG="calib_mc_v5.progress"
TARGETS="car=0.776,ride=0.1627,walk=0.0366,pt=0.018,bike=0.0068"
CONV_CAR="2.0"; CONV_RIDE="1.5"; MAXPASS=5
# seeds = pass-5 ASCs from v2 (post pass-4 re-anchor); warm plans = v2 pass 4 output
CAR=0.00; PT=2.0378; RIDE=-4.1001; WALK=-1.1553; BIKE=-4.0641   # converged ASCs, recalibrating under corrected $31.8/h(2023$) anchor
POP="output_calib_v3/touchup_income/output_plans.xml.gz"
FLOWCAP=0.0201; STORCAP=0.0800
log(){ echo "$(date '+%H:%M:%S') $*" | tee -a "$PROG"; }
: > "$PROG"
for PASS in $(seq 1 $MAXPASS); do
    OUT="output_calib_v5/pass${PASS}"
    rm -rf "$OUT"; mkdir -p output_calib_v5
    log "=== PASS $PASS (warm from $(basename $(dirname $POP))) | ASC car=$CAR pt=$PT ride=$RIDE walk=$WALK bike=$BIKE ==="
    "$JAVA" -Xmx8g -Dmodechoice=true \
        -Dasc.car=$CAR -Dasc.pt=$PT -Dasc.ride=$RIDE -Dasc.walk=$WALK -Dasc.bike=$BIKE \
        -cp "$JAR" de.umd.matsim.RunBaltimoreToll \
        "$NET" "$POP" "$SCHED" "$VEH" "$OUT" 30 $FLOWCAP $STORCAP "$TOLL" \
        > "output_calib_v5/pass${PASS}.log" 2>&1
    RC=$?
    [ $RC -ne 0 ] && { log "PASS $PASS FAILED rc=$RC"; exit 1; }
    RES=$(TARGETS="$TARGETS" AMP=1.0 CLAMP=4.0 python3 ../02_i695_congestion_pricing/reanchor_asc.py \
          "$OUT/modestats.csv" "$CAR" "$PT" "$RIDE" "$WALK" "$BIKE")
    echo "$RES" | grep -E '^#' | tee -a "$PROG"
    CARG=$(echo "$RES" | grep '^CAR_GAP_PP=' | cut -d= -f2)
    RIDEG=$(echo "$RES" | grep '^RIDE_GAP_PP=' | cut -d= -f2)
    read -r NCAR NPT NRIDE NWALK NBIKE < <(echo "$RES" | grep '^ASC_VALUES' | awk '{print $2,$3,$4,$5,$6}')
    cp "$OUT/modestats.csv" "output_calib_v5/pass${PASS}_modestats.csv"
    rm -rf "$OUT/ITERS"
    [ $PASS -ge 2 ] && rm -rf "output_calib_v5/pass$((PASS-1))/output_plans.xml.gz"
    log "PASS $PASS done | car gap ${CARG}pp ride gap ${RIDEG}pp"
    if awk "BEGIN{exit !(${CARG} <= ${CONV_CAR} && ${RIDEG} <= ${CONV_RIDE})}"; then
        log "=== CONVERGED pass $PASS | FROZEN ASC car=$CAR pt=$PT ride=$RIDE walk=$WALK bike=$BIKE ==="
        echo "$CAR $PT $RIDE $WALK $BIKE" > output_calib_v5/FROZEN_ASCS.txt
        exit 0
    fi
    CAR=$NCAR; PT=$NPT; RIDE=$NRIDE; WALK=$NWALK; BIKE=$NBIKE
    POP="$OUT/output_plans.xml.gz"
done
log "NOT converged in $MAXPASS passes"; exit 2
