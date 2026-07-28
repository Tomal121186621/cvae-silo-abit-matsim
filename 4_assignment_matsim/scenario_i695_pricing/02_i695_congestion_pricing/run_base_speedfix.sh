#!/usr/bin/env bash
# Full-pop hybrid base in ONE run, on the CORRECTED (freeway-speed-fixed) network.
# Identical to run_base_full.sh (RunBaltimoreToll fixed modes = ReRoute+TimeAllocationMutator+ChangeExpBeta,
# same resident ABIT population, TOLL=NONE, 64 iters, 11 threads, plan.memory=3, full outputs) EXCEPT the
# network is bmr_network_pt_speedcal_fixed.xml.gz (motorways 65 mph / tunnels 50, vs the broken 47).
# Meant to be launched FULLY DETACHED (detach.py) so it survives the ~1h background-job reaper. On clean
# completion it drops FINAL_ITER + base_speedfix_DONE so the gate poller fires validation automatically.
# STEP 1 of 2 — resident-only (no through-traffic yet); step 2 adds through-traffic.
set -uo pipefail
cd "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim/scenarios/02_i695_congestion_pricing"

MAT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
FIXED_NET="$MAT/network_validation_2023/network_audit/bmr_network_pt_speedcal_fixed.xml.gz"

rm -rf output_base/base_speedfix output_base/base_speedfix_DONE
NET="$FIXED_NET" WRITE=true THREADS=11 PLANMEM=3 XMX=13g \
    bash run_toll.sh "$PWD/output_base/base_speedfix" 64 NONE
RC=$?
if [ $RC -eq 0 ] && [ -f output_base/base_speedfix/output_events.xml.gz ]; then
    echo "64" > output_base/base_speedfix/FINAL_ITER
    touch output_base/base_speedfix_DONE
    echo "$(date) base_speedfix COMPLETE (rc=0) -> DONE marker written"
else
    echo "$(date) base_speedfix did NOT complete cleanly (rc=$RC) -- no DONE marker"
fi
