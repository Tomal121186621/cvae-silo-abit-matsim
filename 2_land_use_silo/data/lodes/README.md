# LEHD LODES origin-destination data (Version 8, JT00)

Source: U.S. Census Bureau, Longitudinal Employer-Household Dynamics program,
https://lehd.ces.census.gov/data/lodes/LODES8/md/od/

| File | Vintage | Role |
|---|---|---|
| `md_od_main_JT00_2021.csv.gz`, `md_od_aux_JT00_2021.csv.gz` | 2021 | Vintage used in the paper pipeline (county-level home-to-work anchoring of workplace assignment) |
| `md_od_main_JT00_2023.csv.gz`, `md_od_aux_JT00_2023.csv.gz` | 2023 | Latest release (2025-12-18), retrieved 2026-07-29; provided for reproduction with newer data |

`main` covers workers living and working in Maryland; `aux` covers workers
living out of state with Maryland workplaces. Commute structure is stable
across vintages (state-level inflow share 24.1% in 2021, 24.6% in 2023).
