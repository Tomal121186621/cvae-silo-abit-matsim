#!/usr/bin/env bash
# Auto-run the base_speedfix validation the moment base_speedfix finishes (STEP 1: corrected network,
# resident-only, no through-traffic yet). Poll until the DONE marker, then run the facility-stratified
# validator (validate_base_hybrid.py) redirected via NETVAL_* env into network_validation_2023/base_speedfix/,
# evaluate gate.json, write STATUS. Does NOT launch any toll run.
set -uo pipefail

MAT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
SCEN="$MAT/scenarios/02_i695_congestion_pricing"
RUN="$SCEN/output_base/base_speedfix"
VDIR="$MAT/network_validation_2023/base_speedfix"
LOG="$SCEN/output_base/validation_gate_speedfix.log"
mkdir -p "$VDIR"
echo "[gate] $(date) waiting for base_speedfix to finish ..." | tee "$LOG"

# 1) poll until the run drops its DONE marker
until [ -f "$SCEN/output_base/base_speedfix_DONE" ]; do
    sleep 60
done
echo "[gate] $(date) base_speedfix DONE; running validation ..." | tee -a "$LOG"

# 2) validation — redirect the shared infra at the base_speedfix run/output subdir
export NETVAL_OUTDIR="scenarios/02_i695_congestion_pricing/output_base/base_speedfix"
export NETVAL_ITER="$(cat "$RUN/FINAL_ITER" 2>/dev/null || echo 64)"
export NETVAL_SUB="base_speedfix"
echo "[gate] NETVAL_OUTDIR=$NETVAL_OUTDIR NETVAL_ITER=$NETVAL_ITER NETVAL_SUB=$NETVAL_SUB" | tee -a "$LOG"
python3 "$MAT/code/validate_base_hybrid.py" >> "$LOG" 2>&1

if [ ! -f "$VDIR/gate.json" ]; then
    echo "[gate] ERROR: gate.json not produced — validation failed. See $LOG" | tee -a "$LOG"
    echo "validation did not produce gate.json" > "$VDIR/GATE_FAILED.txt"; exit 1
fi
PASS=$(python3 -c "import json;print(json.load(open('$VDIR/gate.json'))['GATE_PASS'])")
echo "[gate] GATE_PASS=$PASS" | tee -a "$LOG"

if [ "$PASS" != "True" ]; then
    python3 -c "import json;d=json.load(open('$VDIR/gate.json'));print('FAILED checks:');[print(' ',k,v) for k,v in d['checks'].items() if not v['pass']]" \
        | tee "$VDIR/GATE_FAILED.txt" | tee -a "$LOG"
fi

cat > "$VDIR/STATUS.txt" <<EOF
base_speedfix validation (STEP 1: corrected freeway-speed network, resident-only, NO through-traffic yet).
GATE_PASS=$PASS  (see gate.json, VALIDATION_HYBRID.md, standards_table.csv)
NOTE: resident-only base -> absolute volumes still ~-35% low (that is STEP 2 = add through-traffic);
      but freeway SPEEDS / travel-times are now realistic (motorways 65 mph vs broken 47) and the
      I-95/diversion pattern should be better than base_hybrid.
Compare against: network_validation_2023/base_hybrid/ (broken-network base, kept for reference).
EOF
echo "[gate] $(date) DONE. Validation written to $VDIR (STOPPED; no toll run)." | tee -a "$LOG"
