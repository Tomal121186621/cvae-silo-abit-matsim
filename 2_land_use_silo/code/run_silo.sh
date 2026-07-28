#!/bin/bash
# Run SILO with the corrected engine + native HDF5 + classpath.
# Usage: run_silo.sh <properties_file> [logfile]
# The properties file sets scenario.name, base.year, end.year, and the calibration CSV is read
# automatically from input/assumptions/calibration_by_state.csv (per-state frozen levers).
set -e
PROPS="${1:?usage: run_silo.sh <properties> [logfile]}"
LOG="${2:-/dev/stdout}"
SMOKE="/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test"
US="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated SILO"
JAVA="/Library/Java/JavaVirtualMachines/temurin-21-x64.jdk/Contents/Home/bin/java"
cd "$SMOKE"
"$JAVA" -Xmx12g -Djava.library.path="$US/nativelib" \
    -cp "$(cat /tmp/silo_cp_full.txt)" \
    de.tum.bgu.msm.run.SiloMstm "$PROPS" > "$LOG" 2>&1
echo "SILO_EXIT=$?"
