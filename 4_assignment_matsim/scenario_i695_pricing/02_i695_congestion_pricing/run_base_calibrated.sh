#!/bin/bash
cd "$(dirname "$0")"
NET="$PWD/../../network_validation_2023/network_audit/bmr_network_pt_speedcal_fixed.xml.gz" PLANS="$PWD/../01_base_no_pricing/input/matsim_population_abit_bmr_v7.xml.gz" FLOWCAP=0.10 STORCAP=0.18 WRITE=true THREADS=11 PLANMEM=3 XMX=13g \
  bash run_toll.sh "$PWD/output_base/base_calibrated" 64 NONE
touch "$PWD/output_base/base_calibrated/FINAL_ITER" "$PWD/output_base/base_calibrated_DONE"
