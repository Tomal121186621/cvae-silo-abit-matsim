#!/usr/bin/env bash
# v17mc VERIFICATION: full population, 40 it, SubtourModeChoice ON with the FROZEN calibrated ASCs
# (from output_calib_v3/FROZEN_ASCS.txt), v14kb network + existing MDTA tolls + v14demand population
# (directional gateways). Validates: mode shares vs RTS/ABIT + full AADT suite + cross-harbor screenline.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
read -r CAR PT RIDE WALK BIKE < output_calib_v3/FROZEN_ASCS.txt
echo "frozen ASCs: car=$CAR pt=$PT ride=$RIDE walk=$WALK bike=$BIKE"
exec /Library/Java/JavaVirtualMachines/temurin-21-x64.jdk/Contents/Home/bin/java -Xmx13g \
  -Dmodechoice=true -Dincome.vot.elasticity=0.6 -Dasc.car=$CAR -Dasc.pt=$PT -Dasc.ride=$RIDE -Dasc.walk=$WALK -Dasc.bike=$BIKE \
  -cp "$ROOT/code/matsim-run/target/baltimore-matsim-1.0.jar" de.umd.matsim.RunBaltimoreToll \
  "$ROOT/network_validation_2023/network_audit/bmr_network_pt_speedcal_capfix_v14kb.xml.gz" \
  "$ROOT/scenarios/01_base_no_pricing/input/matsim_population_abit_bmr_v14demand.xml.gz" \
  "$ROOT/input/pt/schedule_mapped.xml.gz" \
  "$ROOT/input/pt/transitVehicles.xml.gz" \
  "$ROOT/scenarios/01_base_no_pricing/output_base_v17mc" \
  40 0.10 0.40 \
  "$ROOT/scenarios/01_base_no_pricing/input/roadpricing_existing_2023.xml"
