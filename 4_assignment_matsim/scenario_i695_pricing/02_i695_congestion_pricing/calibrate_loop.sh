#!/usr/bin/env bash
# Autonomous ASC re-anchor loop for the I-695 no-toll base (Phase 1).
#   - runs 50-iter subsample (50k) passes back-to-back on the ride-fixed corrected scorer (disk-light),
#   - re-anchors ASCs after each (ASC += amp*ln(target/sim), car frozen, near-target freeze),
#   - stops when the worst per-mode gap <= CONV_PP, FREEZES those ASCs,
#   - then runs the FULL 280k base with the frozen ASCs (plan.memory=3, full outputs) for verification.
# Cleans each pass's ITERS after reading modestats; aborts a pass on non-zero exit or low disk.
set -uo pipefail

cd "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim/scenarios/02_i695_congestion_pricing"
SUB="$PWD/input/pop_sub50k.xml.gz"
PROG="output_base/calib_loop.progress"
# Converge on the two policy-relevant, non-floored modes: car and ride. walk/bike hit a structural
# short-trip floor (~5%/2.5%) that can't reach ABIT's 2.8%/0.8%, so they're ACCEPTED at their floors
# (ASC capped at -4.5); requiring them to hit target would loop forever.
CONV_CAR_PP="3.5"     # converged when |car gap| <= this (with walk/bike/pt at floors, car maxes ~73%)
CONV_RIDE_PP="2.0"    # AND |ride gap| <= this (ride is the only actively-anchored mode)
MAXPASS=12
: >> "$PROG"

log(){ echo "$(date '+%H:%M:%S') $*" | tee -a "$PROG"; }

# seed = pass-6 ASCs: walk/bike/pt FROZEN at their pass-5 floor-holding values; only ride re-anchored.
CAR=0.0000; PT=4.0023; RIDE=-2.6868; WALK=-3.6331; BIKE=-8.3817

FROZEN=""
for PASS in $(seq 6 $MAXPASS); do
    OUT="$PWD/output_base/sub_pass${PASS}"
    rm -rf "$OUT"
    log "=== PASS $PASS start | ASCs car=$CAR pt=$PT ride=$RIDE walk=$WALK bike=$BIKE ==="
    WRITE=false PLANS="$SUB" FLOWCAP="0.0179" STORCAP="0.0232" PLANMEM="5" \
        bash run_toll.sh "$OUT" 50 NONE "$CAR" "$PT" "$RIDE" "$WALK" "$BIKE" > "output_base/sub_pass${PASS}.log" 2>&1
    RC=$?
    if [ $RC -ne 0 ]; then log "PASS $PASS FAILED (rc=$RC) -- see sub_pass${PASS}.log"; exit 1; fi

    RES=$(AMP=2.0 CLAMP=3.0 FREEZE_MODES="pt,walk,bike" python3 reanchor_asc.py "$OUT/modestats.csv" "$CAR" "$PT" "$RIDE" "$WALK" "$BIKE")
    echo "$RES" | grep -E '^#|GAP_PP' | tee -a "$PROG"
    CARG=$(echo "$RES" | grep '^CAR_GAP_PP=' | cut -d= -f2)
    RIDEG=$(echo "$RES" | grep '^RIDE_GAP_PP=' | cut -d= -f2)
    read -r NCAR NPT NRIDE NWALK NBIKE < <(echo "$RES" | grep '^ASC_VALUES' | awk '{print $2,$3,$4,$5,$6}')

    cp "$OUT/modestats.csv" "output_base/sub_pass${PASS}_modestats.csv"
    rm -rf "$OUT/ITERS" "$OUT"
    FREEKB=$(df -k . | tail -1 | awk '{print $4}'); FREEGB=$((FREEKB/1024/1024))
    log "PASS $PASS done | car gap ${CARG}pp, ride gap ${RIDEG}pp | disk ${FREEGB}GB free"

    if awk "BEGIN{exit !(${CARG} <= ${CONV_CAR_PP} && ${RIDEG} <= ${CONV_RIDE_PP})}"; then
        FROZEN="$CAR $PT $RIDE $WALK $BIKE"
        log "=== CONVERGED at pass $PASS (car ${CARG}pp<=${CONV_CAR_PP}, ride ${RIDEG}pp<=${CONV_RIDE_PP}; walk/bike accepted at floors) ==="
        log "FROZEN ASCs: car=$CAR pt=$PT ride=$RIDE walk=$WALK bike=$BIKE"
        break
    fi
    CAR=$NCAR; PT=$NPT; RIDE=$NRIDE; WALK=$NWALK; BIKE=$NBIKE
done

if [ -z "$FROZEN" ]; then log "NOT converged within $MAXPASS passes -- stopping before the full base."; exit 2; fi

# --- FULL 280k base with the frozen ASCs (full outputs for validation) ---
read -r FCAR FPT FRIDE FWALK FBIKE <<< "$FROZEN"
BASEOUT="$PWD/output_base/base_full"
rm -rf "$BASEOUT"
log "=== FULL 280k BASE start | frozen ASCs car=$FCAR pt=$FPT ride=$FRIDE walk=$FWALK bike=$FBIKE | plan.memory=3, full outputs ==="
WRITE=true PLANMEM=3 XMX=13g \
    bash run_toll.sh "$BASEOUT" 64 NONE "$FCAR" "$FPT" "$FRIDE" "$FWALK" "$FBIKE" > "output_base/base_full.log" 2>&1
RC=$?
log "=== FULL BASE finished (rc=$RC) ==="
[ -f "$BASEOUT/modestats.csv" ] && tail -1 "$BASEOUT/modestats.csv" | tee -a "$PROG"
log "DONE."
