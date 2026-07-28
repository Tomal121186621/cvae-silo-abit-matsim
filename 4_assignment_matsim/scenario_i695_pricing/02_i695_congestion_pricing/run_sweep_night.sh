#!/bin/bash
ROOT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
CAL="$ROOT/scenarios/02_i695_congestion_pricing"
JAVA=/Library/Java/JavaVirtualMachines/temurin-21-x64.jdk/Contents/Home/bin/java
run() {  # name tollfile
  "$JAVA" -Xmx10g -Dmodechoice=true -Dinnovoff=1.0 -Dsmc.weight=0.04 \
    -Dasc.car=0.0 -Dasc.pt=0.75 -Dasc.ride=-0.60 -Dasc.walk=0.10 -Dasc.bike=-2.10 \
    -cp "$ROOT/code/matsim-run/target/baltimore-matsim-1.0.jar" de.umd.matsim.RunBaltimoreToll \
    "$ROOT/network_validation_2023/network_audit/bmr_network_pt_speedcal_capfix_v14kb.xml.gz" \
    "$CAL/background_calibration/plans_loaded_v4.xml.gz" \
    "$ROOT/input/pt/schedule_mapped.xml.gz" "$ROOT/input/pt/transitVehicles.xml.gz" \
    "$CAL/runs/$1" 15 0.10 0.40 "$2" > "$CAL/runs/$1.log" 2>&1
  cd "$CAL/runs/$1" && ls ITERS | grep -v "^it.15$" | xargs -I{} rm -rf ITERS/{} 2>/dev/null
  rm -f "$CAL/runs/$1/output_allVehicles.xml.gz" "$CAL/runs/$1/output_legs.csv.gz" "$CAL/runs/$1/output_activities.csv.gz"
}
run loaded_tollA "$CAL/toll/roadpricing_i695A_plus_existing.xml"
run loaded_tollB "$CAL/toll/roadpricing_i695B_plus_existing.xml"
echo "SWEEP NIGHT DONE" > "$CAL/runs/sweep_night.done"
