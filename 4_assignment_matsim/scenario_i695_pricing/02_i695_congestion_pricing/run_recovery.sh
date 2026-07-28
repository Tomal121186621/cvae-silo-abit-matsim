#!/bin/bash
ROOT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
CAL="$ROOT/scenarios/02_i695_congestion_pricing"
JAVA=/Library/Java/JavaVirtualMachines/temurin-21-x64.jdk/Contents/Home/bin/java
# 1) tollA dump: 0 iterations on the converged tollA plans -> events + linkstats
"$JAVA" -Xmx10g -Dmodechoice=true -Dinnovoff=1.0 -Dsmc.weight=0.04 \
  -Dasc.car=0.0 -Dasc.pt=0.75 -Dasc.ride=-0.60 -Dasc.walk=0.10 -Dasc.bike=-2.10 \
  -cp "$ROOT/code/matsim-run/target/baltimore-matsim-1.0.jar" de.umd.matsim.RunBaltimoreToll \
  "$ROOT/network_validation_2023/network_audit/bmr_network_pt_speedcal_capfix_v14kb.xml.gz" \
  "$CAL/runs/loaded_tollA/ITERS/it.15/15.plans.xml.gz" \
  "$ROOT/input/pt/schedule_mapped.xml.gz" "$ROOT/input/pt/transitVehicles.xml.gz" \
  "$CAL/runs/loaded_tollA_dump" 0 0.10 0.40 \
  "$CAL/toll/roadpricing_i695A_plus_existing.xml" > "$CAL/runs/loaded_tollA_dump.log" 2>&1
# 2) tollB full rerun with inline slimming
rm -rf "$CAL/runs/loaded_tollB"
"$JAVA" -Xmx10g -Dmodechoice=true -Dinnovoff=1.0 -Dsmc.weight=0.04 \
  -Dasc.car=0.0 -Dasc.pt=0.75 -Dasc.ride=-0.60 -Dasc.walk=0.10 -Dasc.bike=-2.10 \
  -cp "$ROOT/code/matsim-run/target/baltimore-matsim-1.0.jar" de.umd.matsim.RunBaltimoreToll \
  "$ROOT/network_validation_2023/network_audit/bmr_network_pt_speedcal_capfix_v14kb.xml.gz" \
  "$CAL/background_calibration/plans_loaded_v4.xml.gz" \
  "$ROOT/input/pt/schedule_mapped.xml.gz" "$ROOT/input/pt/transitVehicles.xml.gz" \
  "$CAL/runs/loaded_tollB" 15 0.10 0.40 \
  "$CAL/toll/roadpricing_i695B_plus_existing.xml" > "$CAL/runs/loaded_tollB.log" 2>&1 &
BPID=$!
# slim tollB ITERS while it runs (keep only newest 2), guard disk
while kill -0 $BPID 2>/dev/null; do
  sleep 300
  cd "$CAL/runs/loaded_tollB/ITERS" 2>/dev/null && ls -t | tail -n +3 | xargs -I{} rm -rf "{}" 2>/dev/null
done
echo "RECOVERY DONE" > "$CAL/runs/recovery.done"
