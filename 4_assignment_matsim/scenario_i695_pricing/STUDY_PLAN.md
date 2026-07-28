# I-695 Congestion Pricing Study — MATSim

**Objective:** Quantify the traffic and behavioral effects of **time-of-day, link-based congestion pricing on I-695** (Baltimore Beltway), by comparing two scenarios and analyzing the response by subpopulation (income, home location, age, race).

## Scenarios
| | folder | description |
|---|---|---|
| **S1 — No Pricing** | `01_base_no_pricing/` | Validated 2023 base assignment (SILO calib5 → tour-based demand → MATSim), no toll |
| **S2 — Congestion Pricing** | `02_i695_congestion_pricing/` | Same demand/network + I-695 time-of-day link tolls + behavioral response |
| **Comparison** | `comparison/` | Δvolume, rerouting, mode shift, departure-time shift — sliced by subpopulation |

## Design decisions (confirmed with user)
- **Behavioral response = HYBRID:**
  - **Route + departure-time shift** → inside MATSim via the `roadpricing` contrib (agents re-route/re-time to avoid tolls; keeps per-agent SILO tags)
  - **Mode shift** → outer MITO loop using our **existing tour-based mode choice, which is ALREADY price-elastic**. No VOT to add: the Apollo re-spec fixed `b_time = −0.025` and derives `b_cost = b_time / VOT` per person, with an **income-dependent VOT** (USDOT 2016: 50% of hourly household income, purpose-adjusted; commute ~$22/hr, personal ~$19/hr). The apply engine already computes this (`apply_plans.py:333`), so **adding the I-695 toll to auto cost flows straight through to mode choice** — with income-differentiated sensitivity (low-income → larger |b_cost| → more deterred).
- **Subpopulation dimensions (all four):** income, home location, age, race — tagged from SILO on every agent; income-equity is the headline **and falls out directly from the income-dependent VOT.**

## Phases
0. **Base validation** (`../network_validation_2023/`) — validate MATSim `mstm2023` vs **AADT 2023 + FHWA TMAS 2023**; calibrate network (add through-traffic + trucks from TMAS class data to close the freeway gap). Output = S1.
1. **Toll research** (`toll_research/`) — deep research on MD time-of-day toll schemes (I-95 ETL, MD-200 ICC, I-495/270 managed lanes, MDTA); design a defensible I-695 time-of-day link toll schedule.
2. **Behavioral capability** — MATSim roadpricing config for route/time. Mode choice needs **no repair** (already income-VOT price-elastic); just wire the toll into the apply-time auto cost. **Validate** the resulting toll elasticity magnitude against observed MD-facility diversion rates (from Phase 1) to confirm it's credible.
3. **Run S1 & S2** — each to converged congested skims (feedback loop).
4. **Comparison + equity** (`comparison/`) — link Δvolume/VC on I-695 + diversion routes (I-95, I-83, US-40, arterials); mode/time/route shift; subpopulation tables + TRB figures.

## Key risk
Mode-choice inelasticity to price is the central methodological hurdle — Phase 2 must produce a *defensible, literature-consistent* cost elasticity, validated against observed toll-diversion elasticities from the MD facilities (Phase 1).
