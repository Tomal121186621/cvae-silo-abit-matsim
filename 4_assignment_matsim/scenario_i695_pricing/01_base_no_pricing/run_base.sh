#!/usr/bin/env bash
# I-695 study — Scenario S1: BASE, No-Pricing MATSim assignment of the ABIT tour-based demand.
#
# Demand  : ABIT finalized plan (273,742 persons, 10% MSTM sample, BMR-touching tours).
#           Modes are FIXED (mode choice is upstream in ABIT); MATSim assigns routes + departure times only.
# Network : pt2matsim Baltimore network with pt links (input/network/bmr_network_pt.xml.gz).
# Sample  : 10%  ->  flowCapFactor 0.10, storageCapFactor 0.13.
# Replan  : ReRoute(0.15) + TimeAllocationMutator(0.10) + ChangeExpBeta(0.75 selector); innovation off in last 20%.
# Output  : link volumes (linkStats), events, and output_network in ./output/ for AADT/TMAS 2023 validation.
#
# Usage: bash run_base.sh [iterations] [flowCap] [storageCap]
set -euo pipefail

MAT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
SCEN="$MAT/scenarios/01_base_no_pricing"
JAR="$MAT/code/matsim-run/target/baltimore-matsim-1.0.jar"
NET="$MAT/input/network/bmr_network_pt.xml.gz"
PLANS="$SCEN/input/matsim_population_abit_bmr.xml.gz"
SCHED="$MAT/input/pt/schedule_mapped.xml.gz"
VEH="$MAT/input/pt/transitVehicles.xml.gz"
OUT="$SCEN/output"

ITER="${1:-64}"
FLOWCAP="${2:-0.10}"
STORCAP="${3:-0.13}"

export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
"$JAVA_HOME/bin/java" -Xmx13g -cp "$JAR" de.umd.matsim.RunBaltimore \
    "$NET" "$PLANS" "$SCHED" "$VEH" "$OUT" "$ITER" "$FLOWCAP" "$STORCAP"
