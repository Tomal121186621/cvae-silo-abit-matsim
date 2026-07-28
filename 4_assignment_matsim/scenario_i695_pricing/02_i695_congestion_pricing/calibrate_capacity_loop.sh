#!/usr/bin/env bash
# Component 3+4 -- autonomous per-facility CAPACITY calibration to the CALIBRATION station set,
# then a frozen full-280k run + out-of-sample validation on the held-out set.
#
# Each pass: edit the corrected network's per-facility capacities (caps.json) -> run the 50k subsample
# (fixed modes = route+time only; mode choice OFF; 50 iters; disk cleaned each pass) -> validate the
# CALIBRATION set -> SPSA-lite capacity update -> repeat until CALIBRATION corr2>=0.85 & dCorr2<0.01 or
# 6 passes. Capacity only REDISTRIBUTES resident traffic (route balance), it does not raise the level.
#
# NOTE: linkstats require WRITE=true (write.outputs=false suppresses linkStats in RunBaltimoreToll), so
# each pass writes full subsample outputs and is rm-ed immediately after the gate json is read. Peak disk
# = one pass (~0.3 GB) + the final full run (~1.5 GB).
#
# Launch DETACHED so it survives the ~1h background reaper:
#   python3 detach.py output_base/capcal_loop.out bash calibrate_capacity_loop.sh
set -uo pipefail

cd "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim/scenarios/02_i695_congestion_pricing"
MAT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
CODE="$MAT/code"
FIXED_NET="$MAT/network_validation_2023/network_audit/bmr_network_pt_speedcal_fixed.xml.gz"
SUB="$PWD/input/pop_sub50k.xml.gz"
CALIB="$MAT/network_validation_2023/calibration/calibration_stations_2023.csv"
HOLD="$MAT/network_validation_2023/calibration/validation_holdout_2023.csv"
WORK="$PWD/output_base/capcal"
PROG="$PWD/output_base/capcal.progress"
mkdir -p "$WORK"; : >> "$PROG"

# 50k subsample qsim scaling (proven in calibrate_loop.sh: 0.10 * 50124/280674 ~= 0.0179).
FLOWCAP="0.0179"; STORCAP="0.0232"
CONV_CORR2="0.85"; MAXPASS=6

log(){ echo "$(date '+%H:%M:%S') $*" | tee -a "$PROG"; }

# seed caps: principal 0.67 (1500->1005/lane, audit fix); freeway/minor/collector/ramp unchanged.
echo '{"freeway":1.0,"principal":0.67,"minor":1.0,"collector":1.0,"ramp":1.0}' > "$WORK/caps_pass1.json"

PREV=-1; FINAL_CAPS=""
for PASS in $(seq 1 $MAXPASS); do
    CAPS="$WORK/caps_pass${PASS}.json"
    NET="$WORK/network_caps_pass${PASS}.xml.gz"
    OUT="$PWD/output_base/cap_pass${PASS}"
    GATE="$WORK/calib_gate_pass${PASS}.json"
    rm -rf "$OUT"
    log "=== PASS $PASS start | caps $(cat "$CAPS") ==="

    python3 "$CODE/edit_network_capacity.py" "$FIXED_NET" "$CAPS" "$NET" >> "$PROG" 2>&1 \
        || { log "PASS $PASS edit_network FAILED"; exit 1; }

    NET="$NET" PLANS="$SUB" FLOWCAP="$FLOWCAP" STORCAP="$STORCAP" WRITE=true PLANMEM=5 THREADS=8 XMX=13g \
        bash run_toll.sh "$OUT" 50 NONE > "output_base/cap_pass${PASS}.log" 2>&1
    RC=$?
    if [ $RC -ne 0 ]; then log "PASS $PASS run FAILED (rc=$RC) -- see cap_pass${PASS}.log"; exit 1; fi

    NETVAL_FLOWCAP="$FLOWCAP" python3 "$CODE/validate_resident_targets.py" "$OUT" "$CALIB" "$GATE" 2>&1 | tee -a "$PROG"
    CORR2=$(python3 -c "import json;c=json.load(open('$GATE'))['overall']['corr2'];print(c if isinstance(c,(int,float)) and c==c else -1)")

    rm -rf "$OUT"    # linkstats/events/plans no longer needed; gate json holds the metrics
    FREEGB=$(( $(df -k . | tail -1 | awk '{print $4}') /1024/1024 ))
    log "PASS $PASS done | CALIB corr2=$CORR2 | disk ${FREEGB}GB free"

    NEXT=$((PASS+1))
    python3 "$CODE/capacity_update.py" "$GATE" "$CAPS" "$WORK/caps_pass${NEXT}.json" 2>&1 | tee -a "$PROG"

    DCONV=$(python3 -c "print(1 if ($CORR2>=$CONV_CORR2 and abs($CORR2-($PREV))<0.01) else 0)")
    if [ "$DCONV" = "1" ]; then
        FINAL_CAPS="$CAPS"
        log "=== CONVERGED at pass $PASS (corr2=$CORR2>=$CONV_CORR2, dCorr2<0.01) ==="
        break
    fi
    PREV="$CORR2"
done

# not converged within MAXPASS -> adopt the last-updated caps (caps_pass$((MAXPASS+1)))
if [ -z "$FINAL_CAPS" ]; then
    FINAL_CAPS="$WORK/caps_pass$((MAXPASS+1)).json"
    log "NOT converged in $MAXPASS passes -- adopting last-updated caps for the full run."
fi
log "FINAL caps: $(cat "$FINAL_CAPS")"

# --- frozen FULL 280k run on the final calibrated network (full outputs for validation) ---
FINAL_NET="$WORK/network_caps_final.xml.gz"
python3 "$CODE/edit_network_capacity.py" "$FIXED_NET" "$FINAL_CAPS" "$FINAL_NET" >> "$PROG" 2>&1
BASEOUT="$PWD/output_base/base_capcal"
rm -rf "$BASEOUT" output_base/base_capcal_DONE
log "=== FULL 280k on calibrated net start (WRITE=true, plan.memory=3, THREADS=11) ==="
NET="$FINAL_NET" WRITE=true PLANMEM=3 THREADS=11 XMX=13g \
    bash run_toll.sh "$BASEOUT" 64 NONE > "output_base/base_capcal.log" 2>&1
RC=$?
log "=== FULL 280k finished (rc=$RC) ==="

# --- Component 4: out-of-sample validation on the full calibrated run (full-pop scale x10) ---
if [ $RC -eq 0 ] && [ -d "$BASEOUT/ITERS" ]; then
    python3 "$CODE/validate_resident_targets.py" "$BASEOUT" "$CALIB" "$WORK/final_calib_gate.json"  2>&1 | tee -a "$PROG"
    python3 "$CODE/validate_resident_targets.py" "$BASEOUT" "$HOLD"  "$WORK/final_holdout_gate.json" 2>&1 | tee -a "$PROG"
    echo "64" > "$BASEOUT/FINAL_ITER"; touch output_base/base_capcal_DONE
    log "OOS validation written (final_calib_gate.json + final_holdout_gate.json)."
fi
log "DONE."
