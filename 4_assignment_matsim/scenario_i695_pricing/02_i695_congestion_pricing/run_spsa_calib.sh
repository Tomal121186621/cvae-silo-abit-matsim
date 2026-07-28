#!/usr/bin/env bash
# SPSA count calibration of the fully-loaded I-695 network (MATSim-NYC recipe; arXiv:2008.04762).
#
# Calibrates theta = 14 per-gateway through-inflow scales (+ optional 3 arterial capacity mults) so the
# simulated link volumes match observed 2023 AADT on the CALIBRATION stations, then reports theta*. A final
# full-population run (built from theta*) produces the calibrated base network for the toll analysis.
#
# ** DO NOT launch while the v8 base is assigning ** -- it shares the machine + the baltimore-matsim jar.
# Prereqs (build-time, already produced by the report-only sanity test, safe any time):
#   python ../../code/select_calibration_stations.py     -> spsa_{calibration,holdout}_stations.csv
#
# Cadyts is NOT used (not in the jar; pom defers it). SPSA needs NO jar change -- it drives MATSim from
# outside via the seed scripts + a capacity file, so the current jar works as-is.
#
# Tune via env: SPSA_ITERS (default 15), SPSA_INNER (40), SPSA_CAP_DIMS (0 -> add 3 to calibrate arterials),
#               SPSA_POP / SPSA_SAMPLE / SPSA_FLOWCAP (subsample config), SPSA_A / SPSA_C (gains).
set -euo pipefail
cd "$(dirname "$0")"
MAT="$PWD/../.."

# guard: refuse to run if a MATSim assignment is already active
if pgrep -f "de.umd.matsim.RunBaltimore" >/dev/null 2>&1; then
  echo "ABORT: a MATSim run (RunBaltimore*) is active -- wait for the v8 base to finish before SPSA." >&2
  exit 1
fi

export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
echo "SPSA calibration starting. history -> $MAT/runs/spsa/spsa_history.csv ; theta* -> runs/spsa/theta_best.json"
python3 "$MAT/code/spsa_calibrate.py" "$@"
