#!/usr/bin/env python3
"""Model-strengths report (PDF): every comparative result and number from the
CVAE-vs-IPF and ABIT-vs-trip-based experiments, formatted for writing the discussion."""
import json
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path("/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM")
R = json.load(open(ROOT / "IPF-SILO/outputs/cvae_vs_ipf_metrics.json"))
S = json.load(open(ROOT / "IPF-SILO/outputs/spatial_metrics.json"))
T = json.load(open(ROOT / "MITO-comparison/outputs/abit_vs_tripbased_stats.json"))
OUT = ROOT / "Paper Figures Final/model_strengths_report.pdf"

plt.rcParams.update({"font.family": "serif"})

def text_page(pdf, title, body, fs=9.2, mono=False):
    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.08, 0.94, title, fontsize=15, weight="bold")
    fig.text(0.08, 0.91, body, fontsize=fs, va="top", linespacing=1.55,
             family="monospace" if mono else "serif")
    pdf.savefig(fig); plt.close(fig)

def image_page(pdf, title, img_path, caption=""):
    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.08, 0.94, title, fontsize=13, weight="bold")
    ax = fig.add_axes([0.06, 0.30, 0.88, 0.60])
    ax.imshow(mpimg.imread(img_path)); ax.axis("off")
    if caption:
        fig.text(0.08, 0.26, caption, fontsize=8.5, va="top", linespacing=1.5, wrap=True)
    pdf.savefig(fig); plt.close(fig)

zi, zc = R["ipf"]["zeros"], R["cvae"]["zeros"]
dv = R["ipf"]["diversity"]
mh_i = np.mean([v["tv"] for v in R["ipf"]["marg_hh"].values()])
mh_c = np.mean([v["tv"] for v in R["cvae"]["marg_hh"].values()])
mp_i = np.mean([v["tv"] for v in R["ipf"]["marg_pp"].values()])
mp_c = np.mean([v["tv"] for v in R["cvae"]["marg_pp"].values()])

with PdfPages(OUT) as pdf:
    text_page(pdf, "Model Strengths — Comparative Evidence",
"""Baltimore Metropolitan Region platform: CVAE population synthesis, SILO evolution,
ABIT activity-based demand, MATSim assignment.

This report compiles the head-to-head experiments run on the platform's own data:
  1.  CVAE vs IPF/IPU population synthesis — same PUMS training sample, same
      held-out 2016 test split, same validation suite (IPF-SILO/).
  2.  ABIT (activity-based) vs trip-based MITO comparator vs the Maryland RTS
      household travel survey (MITO-comparison/).

HEADLINE NUMBERS
  CVAE recovers 60% of attribute combinations present only in held-out data
      (44 of 73 cells); IPF recovers 0% — structurally impossible for resampling.
  CVAE emits zero impossible attribute combinations; IPF inherits them from the
      raw survey (e.g., a recorded under-16 spouse).
  CVAE population is replication-free; 56% of IPF households are clones of
      other synthetic households (one PUMS record appears 15 times).
  CVAE synthesizes at traffic-analysis-zone geography (~2,300 residents),
      about 60x finer than the PUMA control geography IPF is bound to —
      with no small-area control tables required.
  ABIT reproduces observed tour structure (43% of RTS tours are multi-stop);
      a trip-based model represents 100% single-trip tours by construction.
  ABIT trip-length distribution tracks the RTS survey shape; the trip-based
      comparator misses the long tail (6% of trips beyond 60 km vs 1% observed).

HONESTY LEDGER (reported alongside, not hidden)
  In-sample joint distributions: strong IPF (full-control IPU on a 219k-household
      same-region seed) is a near-oracle and outperforms the CVAE 3-5x on 2/3-way
      SRMSE. This is memorization vs generalization: reweighted resampling copies
      the sample's joints; a generative model re-estimates them. The generative
      contribution begins where the sample ends (unseen combinations, sub-PUMA
      geography, replication-free synthesis).
  Per-PUMA spatial fidelity is a statistical tie (income TVD 0.122 CVAE vs
      0.126 IPF; age 0.098 vs 0.094) — the CVAE's spatial edge is capability
      below PUMA, certified downstream by county-level ACS validation via SILO.
  ABIT slightly over-chains (more 3-4-trip tours than RTS) and under-generates
      multi-tour days (87% single-tour persons vs 71% observed).""")

    text_page(pdf, "1. CVAE vs IPF/IPU — full metric table",
f"""Design: both methods fit on the identical PUMS TRAIN split; controls for IPU =
all 12 attribute marginals of the held-out TEST split (household: dwelling type,
tenure, autos, income bin; person: age band, gender, race, occupation, license,
relationship, nationality, income bin); household-based IPU (Ye et al.), 120
iterations, weighted resample to 150,000 households. CVAE: trained on the same
train split, generated population sampled to the same size. Scored with the
identical validation-suite code against the identical test split.

METRIC                                          IPF/IPU        CVAE
Marginal TVD, household mean                    {mh_i:.4f}         {mh_c:.4f}
Marginal TVD, person mean                       {mp_i:.4f}         {mp_c:.4f}
2-way joint SRMSE, person                       {R['ipf']['joints_pp']['2way_mean_srmse']:.3f}          {R['cvae']['joints_pp']['2way_mean_srmse']:.3f}
3-way joint SRMSE, person                       {R['ipf']['joints_pp']['3way_mean_srmse']:.3f}          {R['cvae']['joints_pp']['3way_mean_srmse']:.3f}
2-way joint SRMSE, household                    {R['ipf']['joints_hh']['2way_mean_srmse']:.3f}          {R['cvae']['joints_hh']['2way_mean_srmse']:.3f}
3-way joint SRMSE, household                    {R['ipf']['joints_hh']['3way_mean_srmse']:.3f}          {R['cvae']['joints_hh']['3way_mean_srmse']:.3f}
Unseen-combination recovery ({zi['test_only_cells']} cells)          0%              {100*zc['recovery_rate']:.0f}%
Structural violations (per 150k HH)             {R['ipf']['structural'].get('total',0)}              {R['cvae']['structural'].get('total',0)}
Replicated household records                    {100*dv['share_duplicated']:.0f}%             0%
Max single-record replication                   {dv['max_replication']}x             1x
HH income top-6-bin share (obs 6.03%)           {100*R['ipf']['tail']['hh_top6_sim']:.2f}%          {100*R['cvae']['tail']['hh_top6_sim']:.2f}%
Per-PUMA TVD, HH income (mean over 81)          {S['ipf_inc']['mean']:.3f}          {S['cvae_inc']['mean']:.3f}
Per-PUMA TVD, person age (mean over 96)         {S['ipf_age']['mean']:.3f}          {S['cvae_age']['mean']:.3f}
Finest synthesis geography                      PUMA           TAZ (~60x finer)
Small-area control tables required              yes            none

Discussion-ready sentence: "Where a large same-population sample exists,
reweighted resampling is a near-oracle for in-sample joint distributions and no
generative model should be expected to beat it; the generative contribution
begins precisely where the sample ends — recovering 60% of combinations never
seen in training, guaranteeing structural validity, eliminating record
replication, and synthesizing at geographies 60x finer than the control data."
""", fs=7.8, mono=True)

    image_page(pdf, "CVAE advantages over IPF/IPU (figure)",
               ROOT / "IPF-SILO/outputs/fig_cvae_advantages.png",
               "Four dimensions where generation beats reweighting, measured on the same data and "
               "test split. The in-sample joint-error comparison (which strong IPF wins, as expected "
               "for a memorization method) is reported in the table on the previous page.")

    image_page(pdf, "Per-PUMA spatial fidelity (statistical tie)",
               ROOT / "IPF-SILO/outputs/fig_cvae_vs_ipf_spatial.png",
               "Distribution of per-PUMA marginal TVD vs the held-out test split. The tie at PUMA "
               "level, combined with the CVAE's zone-level generation capability, is the honest "
               "framing of the spatial claim.")

    text_page(pdf, "2. ABIT vs trip-based (MITO) vs RTS survey",
f"""Design: ABIT ran on the SILO calib5-2023 population (weekday extracted from its
simulated week; person-coherent 1/7 sample = {T['abit_legs_sampled']:,} legs). Trip-based
comparator: the MITO trip plans as assigned in MATSim (one 2-activity agent per
trip; {T['mito_trips']:,} trips). Observed reference: Maryland RTS household travel
survey, weighted ({T['rts_trips']:,} trips; 57,627 tours; 41,914 persons).

METRIC                                    RTS observed    ABIT      Trip-based
Median trip length (beeline km)           {T['median_km']['rts']:.1f}             {T['median_km']['abit']:.1f}       {T['median_km']['mito']:.1f}
Trips beyond 60 km                        ~1%             ~2%       ~6%
Mean trips per home-based tour            {T['trips_per_tour_mean']['rts']:.2f}            {T['trips_per_tour_mean']['abit']:.2f}      1.00 (structural)
Multi-stop tours (3+ trips)               43%             36%       0% (structural)
Single-tour persons per day               71%             87%       (undefined)

The structural argument: a trip-based model cannot represent trip chaining at
all — every "tour" is a single unlinked trip by construction, so any policy whose
response operates through chains (pricing-induced trip consolidation, park-once
behavior, escort trips) is invisible to it. ABIT reproduces the observed chaining
distribution, with a modest over-chaining bias reported honestly.

Both models inherit the same calibrated upstream stack (CVAE population, SILO
evolution, LODES workplaces), so the comparison isolates the demand-model
architecture itself.""", fs=8.8)

    image_page(pdf, "ABIT vs trip-based vs RTS (figure)",
               ROOT / "MITO-comparison/outputs/fig_abit_vs_tripbased.png",
               "(a) ABIT tracks the observed trip-length distribution; the trip-based comparator "
               "misses the long tail. (b) The chaining panel: trip-based = 100% single-trip tours "
               "by construction (orange). (c) Daily tour frequency, with ABIT's under-generation "
               "of multi-tour days shown honestly.")

print("wrote", OUT)
