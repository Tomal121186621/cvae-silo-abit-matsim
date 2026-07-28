# CVAE–SILO–ABIT–MATSim: An Integrated Deep-Generative Travel-Demand Modeling Platform

Code for the integrated travel-demand platform for the Baltimore metropolitan region described in:

> Tomal, R.S., Cirillo, C., Newmark, G., and Mohiuddin, H. *An Integrated Deep-Generative Land-Use
> and Activity-Based Travel-Demand Modeling Platform.* Presented at the Transportation Research
> Board Annual Meeting.

The platform chains four models, each validated against an independent benchmark before its output
feeds the next stage:

| Stage | Model | Role | Validation benchmark |
|---|---|---|---|
| 1 | **CVAE** (conditional variational autoencoder) | Synthetic population of households and persons | Held-out ACS PUMS test split |
| 2 | **SILO** (land-use microsimulation) | Demographic and locational evolution 2016→2023, six states | ACS PUMS 2021–2023, out of sample, per-bin ±5 pp |
| 3 | **ABIT** (activity-based travel model) | Daily activities, tours, income-VOT mode choice | Regional household travel survey (RTS) + NTD ridership |
| 4 | **MATSim** (dynamic traffic assignment) | Route/departure-time equilibrium; SPSA-calibrated external-station layer | MDOT SHA AADT 2023, TMAS hourly profiles, screenlines |

Two cross-cutting mechanisms make a sub-regional platform close at its boundary: workplace
assignment anchored to LODES administrative home-to-work flows (external commuters), and a
cordon-gateway layer with SPSA count calibration (pure through traffic).

## Repository layout

```
1_population_synthesis_cvae/   PUMA-conditioned CVAE (PyTorch): vaelib/ library, steps/ pipeline,
                               run_all.py end-to-end driver
2_land_use_silo/               SILO run configs (properties/), validation & calibration tooling
                               (code/), engine-modification documentation (docs/), final
                               out-of-sample scorecard (calibration/)
3_activity_based_abit/         ABIT Java sources (Maryland use case: income-VOT mode choice,
                               LODES-anchored workplaces, RTS calibration)
4_assignment_matsim/           MATSim run/calibration code: network build & speed handling,
                               gateway through-OD seeding, SPSA calibration, AADT/TMAS/screenline
                               validation, I-695 road-pricing scenario (toll schemas A/B)
5_analysis_and_figures/        Paper figures, ABIT-vs-trip-based comparison, validation reports
```

## Data availability

All input data are public: ACS PUMS (population synthesis and land-use validation), LEHD LODES
(workplace anchoring), OpenStreetMap and GTFS (network), MDOT SHA AADT, FHWA TMAS, and NPMRDS
(assignment validation). The regional household travel survey is available from the regional MPO on
request. Large intermediate artifacts (synthetic populations, networks, MATSim run outputs) are not
tracked here; they are regenerable from the code and available from the corresponding author on
reasonable request.

The SILO engine itself is the open-source TUM model (https://github.com/msmobility/silo); the
Maryland-fork modifications applied in this study (job-matching fixes, per-state calibration levers,
auto-ownership ASC self-calibration, annual occupation and composition reconciliation) are
documented in `2_land_use_silo/docs/`.

## Requirements

- Python ≥3.10 (PyTorch, pandas, geopandas, matplotlib) — stages 1, 2 (tooling), 4 (calibration/validation), 5
- Java 21 + Maven — stages 3 and 4 (MATSim 2024, pt2matsim)

## Citation

```bibtex
@misc{tomal2026platform_code,
  author = {Tomal, Raas Sarker and Cirillo, Cinzia and Newmark, Gregory and Mohiuddin, Hossain},
  title  = {CVAE--SILO--ABIT--MATSim: An Integrated Deep-Generative Travel-Demand Modeling Platform (code)},
  year   = {2026},
  url    = {https://github.com/Tomal121186621/cvae-silo-abit-matsim}
}
```

## License

MIT — see `LICENSE`.
