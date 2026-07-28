# Updated SILO — land-use run, calibration & validation

Tooling, run configs, calibration and validation artifacts for running SILO 2016→2023 on the
VAE base-year synthetic population (Approach B: calibrate behavioral coefficients once on the
2016–2020 backcast, then forecast 2021–2023 with only exogenous control totals).

```
Updated SILO/
├── code/          # all Python tooling (validators, performance framework, output collector)
├── properties/    # SILO run configs (siloMstm_uvae.properties = the Approach-B run)
├── calibration/   # calibration-window (2016–2020) targets, scalers, calibrated coefficients
├── validation/    # validation outputs vs ACS: summaries, scorecards, floors, figures/
├── docs/          # SILO model & mechanism reference (PDF + markdown sections)
└── nativelib/     # HDF5 native libs (skims) — legacy x86 jhdf5
```

The SILO **engine** (source + jars) lives at `/Users/tomal/Documents/SILO Simulation/silo-master`.
The engine **working dir** (`base.directory`) is `/Users/tomal/Documents/VAE SILO Architecture/silo_smoke_test`.
Per-year microdata is collected into `Pipeline/2_SILO_landuse/output/year_<YEAR>/` (the MITO input).

## Run order
1. Build the engine (see engine repo); run SILO with `properties/siloMstm_uvae.properties`.
2. `python code/collect_yearly_output.py`        — collect microdata → Pipeline output.
3. `SILO_SCEN=<scen> OUT_SUB=<tag> python code/validate_allstates.py 2016 … 2023` — model vs ACS.
4. `python code/compute_floors.py`               — identifiability floors → validation/.
5. `python code/performance_scorecard.py`        — forecast skill vs floors vs baseline.
6. `python code/make_performance_figures.py`     — figure suite → validation/figures/.

See `code/README.md` for per-script detail and `validation/`/`calibration/` for outputs.
