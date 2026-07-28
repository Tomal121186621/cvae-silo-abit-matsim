#!/usr/bin/env bash
# I-695 study — Scenario S1 BASE, No-Pricing — TRANSIT-FIX re-run.
# Identical config to run_base.sh (64 iters, flowCap 0.10, storageCap 0.13, stuckTime 120,
# removeStuckVehicles true, endTime 36h, modes fixed) but assigns the NTD-re-anchored ABIT demand
# (transit 2.05% / car 77.5%, was 9.9% / 69.7%) into a FRESH output dir output_transitfix/
# (output/ preserved as the pre-fix "before" run for comparison).
set -euo pipefail

MAT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
SCEN="$MAT/scenarios/01_base_no_pricing"
JAR="$MAT/code/matsim-run/target/baltimore-matsim-1.0.jar"
NET="$MAT/input/network/bmr_network_pt.xml.gz"
PLANS="$SCEN/input/matsim_population_abit_bmr.xml.gz"
SCHED="$MAT/input/pt/schedule_mapped.xml.gz"
VEH="$MAT/input/pt/transitVehicles.xml.gz"
OUT="$SCEN/output_transitfix"

ITER="${1:-64}"
FLOWCAP="${2:-0.10}"
STORCAP="${3:-0.13}"

export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
"$JAVA_HOME/bin/java" -Xmx13g -cp "$JAR" de.umd.matsim.RunBaltimore \
    "$NET" "$PLANS" "$SCHED" "$VEH" "$OUT" "$ITER" "$FLOWCAP" "$STORCAP"
