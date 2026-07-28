#!/usr/bin/env bash
# v16 = v15 (capfix_v13 network + v15 demand) + EXISTING 2023 MDTA harbor-crossing tolls.
# Runner: RunBaltimoreToll with SubtourModeChoice OFF (default) -> identical architecture to
# RunBaltimore (frozen modes, ReRoute+TimeAllocation+ChangeExpBeta) + roadpricing ($ scored at
# marginalUtilityOfMoney; see MODE_SCORER_MAPPING.md).
set -e
ROOT="/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
exec /Library/Java/JavaVirtualMachines/temurin-21-x64.jdk/Contents/Home/bin/java -Xmx13g \
  -cp "$ROOT/code/matsim-run/target/baltimore-matsim-1.0.jar" de.umd.matsim.RunBaltimoreToll \
  "$ROOT/network_validation_2023/network_audit/bmr_network_pt_speedcal_capfix_v14kb.xml.gz" \
  "$ROOT/scenarios/01_base_no_pricing/input/matsim_population_abit_bmr_v13demand.xml.gz" \
  "$ROOT/input/pt/schedule_mapped.xml.gz" \
  "$ROOT/input/pt/transitVehicles.xml.gz" \
  "$ROOT/scenarios/01_base_no_pricing/output_base_v16_tolled" \
  40 0.10 0.40 \
  "$ROOT/scenarios/01_base_no_pricing/input/roadpricing_existing_2023.xml"
