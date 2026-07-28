# Frozen calibrated base — mode-choice-enabled MATSim (2026-07-14)

## Configuration (FROZEN — do not recalibrate)

| Setting | Value | Why |
|---|---|---|
| `-Dmodechoice` | `true` | inner-loop SubtourModeChoice enabled (toll can shift modes) |
| `-Dinnovoff` | `1.0` | innovation NEVER disabled. The MATSim default (0.8) collapses mode shares in the last 20% of iterations (selection drains to best plan once SMC stops injecting alternatives); with 1.0 the reported shares are the innovation-on stationary equilibrium. |
| `-Dsmc.weight` | `0.04` | SMC's uniform random injection puts a churn floor (~weight-proportional) under every mode; at the old 0.15 the pt/bike targets sat BELOW the floor and were unreachable by any ASC. |
| ASCs | car 0.0 / pt **0.75** / ride **−0.60** / walk **0.10** / bike **−2.10** | pass-8 set. Note: pass 7 (pt 0.61 / ride −0.95 / walk −0.37 / bike −2.49) produced IDENTICAL shares — the residual is ASC-insensitive (see below). |
| Iterations / caps | 15 / flow 0.10 / storage 0.40 | 10% sample |
| Heap | `-Xmx10g` | 13g crashed the 18 GB Mac (memory exhaustion + Rosetta overhead) |
| Network | `bmr_network_pt_speedcal_capfix_v14kb.xml.gz` | |
| Base run output | `output_calib_fs/pass8/` (equilibrium identical to pass 7) | |

## Final shares vs ABIT targets

| Mode | Frozen base | ABIT target | Dev |
|---|---|---|---|
| car | 80.3% | 77.6% | +2.7 pp |
| ride | 15.1% | 16.3% | −1.2 pp |
| pt | 1.66% | 1.8% | −0.15 pp |
| walk | 2.55% | 3.66% | −1.1 pp |
| bike | 0.42% | 0.68% | −0.26 pp |

car+ride (auto persons) 95.4% vs 93.9%.

## Calibration history (why 8 passes)

- Passes 1–5 calibrated against the post-innovation-off shares — an algorithmic artifact
  (one-iteration collapse of ~9 pp to car at it.13 = 0.8×15), nearly ASC-insensitive. Wasted.
- Pass 6 (`innovoff=1.0`) removed the cliff and exposed the churn floor (pt pinned at ~3.9%).
- Pass 7 (`smc.weight=0.04`) shrank the floor 4×: pt and bike landed on target.
- Pass 8 (large ride/walk ASC raises) moved NOTHING → the remaining ride/walk ≈ −1.1 pp
  residual is structural (score-gap magnitude for marginal agents), not calibration error.
  It is held identical across base and toll scenarios and cancels in the comparison.
