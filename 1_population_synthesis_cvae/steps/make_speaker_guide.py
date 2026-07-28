#!/usr/bin/env python3
"""Generate a detailed SPEAKER GUIDE (PDF) for the VAE presentation.
For every slide/figure: what it shows, how to read the axes, the key numbers,
and a suggested talking point. Embeds a thumbnail of each figure.
Output → VAE_Presentation_Speaker_Guide.pdf
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
                                HRFlowable, KeepTogether, PageBreak)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Formula font: base-14 Helvetica cannot render some math glyphs (⊙ ‖ etc.), so
# register a Unicode TTF for the "Formulation" lines. Fall back gracefully.
_UNI_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FORMULA_FONT = "Times-Italic"
for _fp in _UNI_CANDIDATES:
    if Path(_fp).exists():
        try:
            pdfmetrics.registerFont(TTFont("FormulaUni", _fp))
            FORMULA_FONT = "FormulaUni"
            break
        except Exception:
            pass

ROOT = Path(__file__).resolve().parents[1]
FV = ROOT / "outputs" / "figures" / "validation"
FT = ROOT / "outputs" / "figures" / "training"
SILO = ROOT.parent / "Updated SILO"
SVFIG = SILO / "validation" / "by_year_acs_calib5" / "figures"
SMD23 = SILO / "validation" / "by_year_acs_calib5" / "2023" / "MD"
MITO = ROOT.parent / "Tour Based MITO"
MFIG = MITO / "validation" / "figures"
MAPP = MFIG / "applied"
MTAB = MITO / "validation" / "tables"
# ABIT (agent-based tour model) + current I-695 MATSim figures
ABITF = ROOT.parent / "ABIT" / "validation" / "rts_tripgen_dist" / "figures"
ABITS = ROOT.parent / "ABIT" / "validation" / "figures_studyarea"
MATF = ROOT.parent / "Updated MATSim" / "network_validation_2023" / "FINAL_FIGURES"
# v7 base-year AADT validation figures (the deck's AADT section 55-89 source)
V7 = ROOT.parent / "Updated MATSim" / "network_validation_2023" / "v7_base"
V7BYROUTE = V7 / "aadt_validation_by_route"
V7SPEED = V7 / "by_speedtier"
# Primary output goes into the deck folder; a synced copy stays at the repo root.
DECK_DIR = ROOT.parent / "Presentation and Misc"
OUT = DECK_DIR / "VAE_Presentation_Speaker_Guide.pdf"
OUT_ROOT = ROOT / "VAE_Presentation_Speaker_Guide.pdf"

# ── Canonical VAE numbers, rendered at build time from the live validation run ──
# Single source of truth so every caption below matches the regenerated figures.
import json as _json
_VAE_RESULTS = ROOT / "outputs" / "07_validation" / "full" / "results.json"
with open(_VAE_RESULTS) as _f:
    _R = _json.load(_f)
_mh = _R["2_marginals_hh"]; _mp = _R["2_marginals_pp"]
_jp = _R["3_joints_pp"]; _sz = _R["9_sampling_zeros"]; _mem = _R["10_memorization"]
_coh = _R["11_coherence"]

def _tv2(v):  # 3-dp to match the figure titles (08_figures.py :.3f); 4-dp only for
    # sub-0.005 values so a tiny TV like gender's 0.0018 keeps a second significant digit.
    return f"{v:.4f}".rstrip("0").rstrip(".") if v < 0.005 else f"{v:.3f}"

_TVH = {k: _tv2(_mh[k]["tv"]) for k in _mh}          # hh marginals
_TVP = {k: _tv2(_mp[k]["tv"]) for k in _mp}          # pp marginals
_UNIQ = _mem["unique_gen_person_types"]
_FRAC_IN = _mem["frac_gen_types_in_train"]
_NOVEL = round(_UNIQ * (1.0 - _FRAC_IN))             # novel person-types
_RECOV = round(_sz["recovery_rate"] * 100)           # sampling-zero recovery %
_SIGINC = _coh["sigma_income_exact_pct"]
_J1 = f"{_jp['1way_mean_srmse']:.2f}"; _J2 = f"{_jp['2way_mean_srmse']:.2f}"
_J3 = f"{_jp['3way_mean_srmse']:.2f}"
_WP = {name: f"{v:.2f}" for name, v in _jp["worst_pairs"]}
def _wp(name):
    return _WP.get(name, "?")

NAVY = HexColor("#1F3A5F"); GREY = HexColor("#444444"); RULE = HexColor("#888888")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Times-Bold", fontSize=16,
                    textColor=NAVY, spaceBefore=14, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Times-Bold", fontSize=13,
                    textColor=NAVY, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=ss["BodyText"], fontName="Times-Roman", fontSize=10.5,
                      leading=14.5, textColor=HexColor("#111111"), spaceAfter=4)
LEAD = ParagraphStyle("LEAD", parent=BODY, textColor=GREY, fontSize=10, spaceAfter=8)
CAP = ParagraphStyle("CAP", parent=BODY, fontSize=9, textColor=GREY, spaceAfter=2)
FRM = ParagraphStyle("FRM", parent=BODY, fontName=FORMULA_FONT, fontSize=10.5, leading=16,
                     textColor=HexColor("#0B2E4F"), leftIndent=14, spaceBefore=1, spaceAfter=1)
FRMNOTE = ParagraphStyle("FRMNOTE", parent=BODY, fontName=FORMULA_FONT, fontSize=9.5, textColor=GREY,
                         leftIndent=14, spaceAfter=3)

story = []


def label_para(label, text):
    return Paragraph(f"<b>{label}:</b> {text}", BODY)


def formula_flowables(formula):
    """Render a Formulation block. `formula` is a str, a list of str lines, or a
    list of (line, note) tuples where note is a small grey gloss under the line."""
    out = [Paragraph("<b>Formulation:</b>", BODY)]
    lines = formula if isinstance(formula, (list, tuple)) else [formula]
    for ln in lines:
        if isinstance(ln, (list, tuple)):
            eq, note = ln
            out.append(Paragraph(eq, FRM))
            if note:
                out.append(Paragraph(note, FRMNOTE))
        else:
            out.append(Paragraph(ln, FRM))
    return out


def thumb(path, max_w=4.4 * inch, max_h=3.0 * inch):
    p = Path(path)
    if not p.exists():
        return Paragraph(f"[missing {p.name}]", CAP)
    iw, ih = Image.open(str(p)).size
    ar = iw / ih
    w, h = max_w, max_w / ar
    if h > max_h:
        h, w = max_h, max_h * ar
    return RLImage(str(p), width=w, height=h)


def figure(title, img, shows, read, numbers, say, formula=None,
           order=("shows", "read", "formula", "numbers", "say")):
    blocks = [Paragraph(title, H2)]
    if img is not None:
        blocks.append(thumb(img))
        blocks.append(Spacer(1, 4))
    lut = {"shows": ("What it shows", shows), "read": ("How to read it", read),
           "numbers": ("Key numbers", numbers), "say": ("What to say", say)}
    for k in order:
        if k == "formula":
            if formula:
                blocks.extend(formula_flowables(formula))
            continue
        lbl, txt = lut[k]
        if txt:
            blocks.append(label_para(lbl, txt))
    blocks.append(Spacer(1, 6))
    blocks.append(HRFlowable(width="100%", thickness=0.5, color=RULE, spaceBefore=2, spaceAfter=8))
    # keep the heading + image + first block together; let the rest flow
    story.append(KeepTogether(blocks[:3]))
    story.extend(blocks[3:])


def section(title, intro=None):
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.4, color=NAVY, spaceAfter=4))
    story.append(Paragraph(title, H1))
    if intro:
        story.append(Paragraph(intro, LEAD))


# ══════════════════════════════════════════════════════════════════════════
# COVER
# ══════════════════════════════════════════════════════════════════════════
story.append(Spacer(1, 40))
story.append(Paragraph("Speaker Guide", ParagraphStyle("T", parent=H1, fontSize=26, spaceAfter=4)))
story.append(Paragraph("A Conditional VAE for Synthetic Population Synthesis",
                       ParagraphStyle("ST", parent=H1, fontSize=15, textColor=GREY)))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "A slide-by-slide guide to what every figure shows, how to read its axes, the numbers that matter, "
    "and a suggested talking point. Read it end-to-end once, then skim the <b>What to say</b> lines before the talk.",
    BODY))
story.append(Paragraph(
    "One-paragraph summary you can memorize: <i>We built a deliberately simple conditional VAE that turns 2016 "
    "Census PUMS microdata into a full synthetic population — households, persons, dwellings, and jobs — for the "
    "96-PUMA Baltimore–Washington region. Income is handled as a bin plus an empirical within-bin dollar draw, "
    "which recovers the heavy income tail. Training is healthy (no overfitting, no posterior collapse) and the "
    "model generalizes rather than memorizes. On a held-out test split it reproduces every single-variable "
    "distribution, the pairwise and higher-order relationships between variables, and produces zero impossible "
    "records.</i>", BODY))
story.append(Spacer(1, 6))
story.append(label_para("Two terms you will use repeatedly",
    "<b>TV (Total Variation)</b> = one number for the distance between two distributions, "
    "½·Σ|p<sub>gen</sub> − p<sub>test</sub>| across categories; 0 means identical, so smaller is better and under ~0.03 "
    "is very good. <b>SRMSE</b> (standardized root-mean-square error) is a similar 'lower-is-better' error used for the "
    "joint tables."))
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════
# CONCEPT SLIDES
# ══════════════════════════════════════════════════════════════════════════
section("1 — Opening & Motivation (title slide)")
figure("Title slide", None,
   shows="The project in one line: a conditional VAE that generates the SILO/MITO base-year synthetic population "
         "from ACS PUMS 2016 for the Baltimore–Washington MSTM region (96 PUMAs across DE, DC, MD, PA, VA, WV).",
   read=None,
   numbers="Inputs: 253,029 sample households / 626,201 persons, weighted to ~4.70M households and ~12.49M persons. "
           "Base year 2016 (incomes put in 2016 dollars via the ACS ADJINC factor).",
   say="Transport microsimulation (SILO → MITO → MATSim) needs a complete, realistic synthetic population to start "
       "from. We generate that population with a generative model trained on real census microdata, and — crucially — "
       "we validate it honestly on data the model never saw during training.")

section("2 — VAE Architecture (diagram slide)")
figure("The model, box by box", None,
   shows="The data flow: a household record (all its attributes plus its people, each one-hot encoded) goes into an "
         "MLP encoder, is compressed into a small Gaussian latent vector z (24 numbers), and an MLP decoder expands z "
         "back out through softmax heads that predict every attribute at once. A conditioning box (the household's "
         "PUMA location + its size) is fed to both encoder and decoder.",
   read="Left-to-right is the generative path. At generation time we skip the encoder: we draw z from a standard "
        "normal, pick a PUMA and a size, and decode to get a brand-new household.",
   numbers="Latent dimension 24; PUMA embedding 8-d; two 256-wide MLP layers each side. Loss = reconstruction "
           "cross-entropy + β·KL with a 'free-bits' floor of 0.5 nat/dim.",
   formula=[
     ("Training objective (conditional ELBO, maximized):",""),
     ("&nbsp;&nbsp;L(x) = E<sub>q(z|x,c)</sub>[ log p(x|z,c) ] − β·D<sub>KL</sub>( q(z|x,c) ‖ p(z|c) )",
      "first term = reconstruction (softmax cross-entropy over every attribute head); second = latent regularizer, "
      "with a free-bits floor so D<sub>KL</sub> per dim can't be driven to 0 (prevents posterior collapse)."),
     ("Reparameterization (lets gradients flow through the sampling):",""),
     ("&nbsp;&nbsp;z = μ + σ ⊙ ε,&nbsp;&nbsp;ε ~ N(0, I)",
      "μ, σ are the encoder outputs; ⊙ is element-wise product. At generation z ~ N(0,I) directly, conditioned on (PUMA, size)."),
   ],
   say="It's deliberately simple — a plain conditional VAE, no autoregressive decoder, no transformer, no special "
       "income network. The single design trick is that the latent z carries the correlations between variables, so "
       "one shared latent reproduces the joint structure. The one embedded variable is location (PUMA); everything "
       "else is one-hot. Two ideas make it work: free-bits on the KL (so the latent can't collapse) and treating "
       "income as a bin plus an empirical dollar draw (so the rich tail survives). Impossible categories are masked "
       "out during decoding, so we can never emit a nonsensical record.")

section("3 — Workplace (Work-Zone) Re-assignment (methodology slide)")
figure("How each worker gets a job zone (and why we re-assign)", None,
   shows="After the population exists, every employed person is (re-)assigned a workplace zone. For a worker at a home "
         "zone we read travel times to all zones from the highway skim, weight each destination by "
         "exp(−β·time) × number of vacant jobs there, sample a zone from that weighted distribution, then decrement "
         "that zone's remaining jobs and create a job record.",
   read="Think of it as a capacity-constrained gravity model: nearer zones and job-rich zones are more likely, but "
        "each zone can only absorb as many workers as it has jobs, so zones fill to their forecast employment.",
   numbers="Friction β = 0.07 (the code value; the design note cites 0.08 as the target), tuned so realized commutes "
           "match the observed work-trip length distribution (~37.6-min target). 6,091,727 workers re-assigned out of "
           "an 8.98M-job forecast; 0 unreachable, 0 external surplus. In SILO, person.workplace stores the JOB id "
           "(not the zone); the job's zone lives in the job table.",
   formula=[
     ("Capacity-constrained gravity draw — worker at home zone o picks work zone d with probability",""),
     ("&nbsp;&nbsp;P(d | o) = J<sub>d</sub> · exp(−β·t<sub>od</sub>) / Σ<sub>d'</sub> J<sub>d'</sub> · exp(−β·t<sub>od'</sub>)",
      "J<sub>d</sub> = vacant jobs in zone d (decremented after each assignment, so zones fill to their forecast "
      "employment); t<sub>od</sub> = highway-skim travel time; friction β = 0.07 (design-note target 0.08), "
      "tuned to the ~37.6-min work-trip length."),
   ],
   say="The word to use here is RE-ASSIGN. Our first workplace pass used the raw commute-time distribution directly as "
       "the friction and multiplied by job counts, which double-counted downtown opportunities and produced commutes "
       "about twice too long — roughly 62 minutes against a 37.6-minute target. We re-assigned every worker's job zone "
       "with a proper distance-decay friction, exp(−β·time) with β = 0.07, which reproduces the real commute-length "
       "distribution. If asked, note the fix continues downstream: the tour-based travel model re-draws each worker's "
       "job zone once more against the survey-estimated (RTS) work-trip impedance — doubly-constrained so job totals "
       "are honored — pulling the median commute from ~26 down to ~16 miles for survey-realistic commutes.")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════
# TRAINING HEALTH
# ══════════════════════════════════════════════════════════════════════════
section("Training Health — the fit is sound and the model generalizes",
        "These four slides answer the two questions a reviewer asks first: did training behave, and did the model "
        "just memorize the data? Answer: healthy convergence, full use of the latent, and clear generalization.")

figure("T1 — ELBO training curves", FT / "T1_elbo_curves.png",
   shows="The training objective (the ELBO / loss) over training epochs, plotted as two lines — one for the training "
         "split, one for the validation split.",
   read="X-axis = epoch (training progress); Y-axis = loss (lower is better). Watch two things: both lines go down "
        "and flatten (convergence), and the two lines stay close together (no overfitting — if the model were "
        "memorizing, validation would peel away and rise while training kept falling).",
   numbers="Train and validation curves descend together and plateau with essentially no gap.",
   say="Training converges smoothly and the validation curve tracks the training curve — there's no divergence, so "
       "we're not overfitting. Validation is also what we used for early stopping.")

figure("T3 — KL & active latent dimensions (collapse monitor)", FT / "T3_kl_active_dims.png",
   shows="Two things over training on one chart: the total KL divergence of the latent (purple, LEFT axis) and the "
         "number of latent dimensions that are actually active (green, RIGHT axis).",
   read="X-axis = epoch. Purple line (left axis, 'KL divergence') falls from ~40 early on and settles around 13 — the "
        "latent stops over-encoding and stabilizes. Green line (right axis, 'active latent dims') sits flat at the top, "
        "at 24. The point is the green line: it stays pinned at the maximum, meaning none of the dimensions die.",
   numbers="All 24 of 24 dimensions stay active (green line flat at 24); KL settles near 13 nats. Contrast: the "
           "earlier v6 model kept only 3–4 of 96 dimensions alive — classic posterior collapse.",
   say="This is the free-bits payoff, and it's the slide to point at when you say 'no posterior collapse.' The green "
       "line never drops off 24 — every latent dimension keeps carrying information, so the model uses its full "
       "capacity to encode the joint structure instead of ignoring the latent and printing the average.")

figure("T2 — Reconstruction loss (train vs validation)", FT / "T2_reconstruction.png",
   shows="The reconstruction part of the loss over training — how well the decoder rebuilds a record after encoding "
         "it — plotted separately for the training and validation splits.",
   read="X-axis = epoch; Y-axis = reconstruction cross-entropy (lower = better rebuild). Both lines drop sharply, "
        "briefly bump up during KL-annealing, then descend together and flatten around ~6.5–7 with only a small "
        "train/validation gap.",
   numbers="Train and validation reconstruction converge close together (small, stable gap) — the decoder recovers "
           "records well on data it never trained on.",
   say="The model can take a real record, compress it to 24 numbers, and rebuild it accurately — and it does that "
       "about as well on held-out records as on training records, so the latent space is genuinely meaningful, not "
       "overfit.")

figure("M — Memorization check (the anti-memorization proof)", FV / "M_memorization.png",
   shows="Whether the generated people are copies of training records or genuinely new-but-valid combinations. Two "
         "bars split the unique generated person 'types' into those that also appear in training ('in train') and "
         "those that do not ('novel').",
   read="Y-axis = percent of generated person-types. Left bar = share seen in training; right bar = share that is "
        "brand new. A model that memorized would push the left bar to ~100% and leave 'novel' near zero; a model that "
        "generalizes produces a substantial 'novel' bar.",
   numbers=f"~{round(_FRAC_IN*100)}% of generated person-types were seen in training and ~{round((1-_FRAC_IN)*100)}% "
           f"are novel — about {_NOVEL:,} valid new person-types ({_UNIQ:,} unique types in total). Related coherence "
           f"checks: ~{_RECOV}% of test-only cells recovered, and Σ person income = household income holds to "
           f"{_SIGINC:.2f}%.",
   say="This is the key 'we didn't memorize' slide. Only about six in ten generated person-types were in the training "
       "data — roughly forty percent are new, valid combinations the model synthesized. So it learned the "
       "distribution and samples from it; it is not regurgitating the census file. And every new record still "
       "respects the hard constraints.")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════
# MARGINALS
# ══════════════════════════════════════════════════════════════════════════
section("Marginals — does each variable, on its own, match reality?",
        "A 'marginal' is the distribution of a single variable ignoring the others (e.g. what fraction of people are "
        "in each age band). These are the most basic fidelity check. Everything here is against the held-out 2016 "
        "test split. Read the TV number in each caption: under ~0.03 is excellent.")

figure("F1 — Marginal TV summary (read this one carefully)", FV / "F1_marginal_TV_summary.png",
   shows="One bar per attribute, giving that attribute's Total-Variation distance between the generated population "
         "and the held-out test — a scorecard of all marginals on a single chart.",
   read="X-axis = the attributes; Y-axis = TV (lower is better). The red horizontal line at 0.03 is the 'very good' "
        "reference. Bars at or below the line are effectively solved; taller bars are the harder variables.",
   numbers=f"Nearly all attributes sit at or below 0.03. Best: gender (TV {_TVP['gender']}), household autos "
           f"({_TVH['autos']}), dwelling type ({_TVH['dwellingType']}). The tallest bars are occupation "
           f"({_TVP['occupation']}), age ({_TVP['age_bin']}), household income bin ({_TVH['income_bin']}).",
   formula=[
     ("Total Variation between the generated and observed (test) category shares of a variable:",""),
     ("&nbsp;&nbsp;TV = ½ · Σ<sub>k</sub> | p<sub>gen</sub>(k) − p<sub>obs</sub>(k) |",
      "sum over categories k; 0 = identical distributions, 1 = disjoint. Under ~0.03 is excellent."),
   ],
   say="This single chart is the headline for marginals: every variable is close to the truth, most of them "
       "extremely close. Where a bar is a little taller — income tail, age, occupation — that's driven by "
       "within-household coupling, which I'll come back to; it's a bounded, understood effect, not a failure.")

MARG = [
 ("F1 — Household dwelling type", "F1_marginal_hh_dwellingType.png",
  "share of households in each dwelling type (single-family, multi-family, etc.)",
  "single-family vs multi-family mix",
  f"TV {_TVH['dwellingType']} — matches almost exactly."),
 ("F1 — Household tenure (own / rent)", "F1_marginal_hh_tenure.png",
  "share of households owning vs renting",
  "the own/rent split",
  f"TV {_TVH['tenure']} — reproduced."),
 ("F1 — Household vehicles (autos)", "F1_marginal_hh_autos.png",
  "share of households with 0, 1, 2, 3+ vehicles",
  "car-ownership levels (important for mode choice downstream)",
  f"TV {_TVH['autos']} — near-perfect."),
 ("F1 — Household income bin", "F1_marginal_hh_income_bin.png",
  "share of households in each income band",
  "the income distribution as bands",
  f"TV {_TVH['income_bin']} — close, with a slight thinning at the very top band that the within-bin dollar draw then repairs."),
 ("F1 — Person age", "F1_marginal_pp_age_bin.png",
  "share of people in each age band",
  "the age pyramid",
  f"TV {_TVP['age_bin']} — tracks ACS across all bands."),
 ("F1 — Person gender", "F1_marginal_pp_gender.png",
  "male/female split",
  "the sex ratio",
  f"TV {_TVP['gender']} — essentially exact."),
 ("F1 — Person race", "F1_marginal_pp_race.png",
  "share of people in each race category",
  "the racial composition",
  f"TV {_TVP['race']} — reproduced."),
 ("F1 — Person occupation", "F1_marginal_pp_occupation.png",
  "share of people in each occupation/employment category",
  "the employment/occupation mix",
  f"TV {_TVP['occupation']} — close."),
 ("F1 — Person driver's license", "F1_marginal_pp_driversLicense.png",
  "share of people holding a driver's license",
  "licensing rate (feeds car use downstream)",
  f"TV {_TVP['driversLicense']} — matches."),
 ("F1 — Person relationship / household role", "F1_marginal_pp_relationship.png",
  "share of people by role in the household (householder, spouse, child, …)",
  "household composition roles",
  f"TV {_TVP['relationship']} — reproduced."),
 ("F1 — Person nationality (foreign-born)", "F1_marginal_pp_nationality.png",
  "share of people who are foreign-born",
  "the immigrant share and where it concentrates",
  "captured including the spatial gradient — e.g. much higher foreign-born share in Northern Virginia than in "
  "Baltimore, matching ACS."),
 ("F1 — Person income bin", "F1_marginal_pp_income_bin.png",
  "share of people in each personal-income band (about 28% have zero earnings)",
  "the personal-income distribution, including non-earners",
  f"TV {_TVP['income_bin']} — close."),
]
for ttl, fn, shows_tail, say_tail, num in MARG:
    figure(ttl, FV / fn,
       shows=f"Two overlaid distributions — generated vs ACS test — of the {shows_tail}.",
       read="Bars/points compare generated (model) against the held-out test for each category; the closer the two, "
            "the better. The caption's TV number summarizes the gap in one figure.",
       numbers=num,
       say=f"Here we're checking {say_tail}. {num}")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════
# JOINT RELATIONSHIPS
# ══════════════════════════════════════════════════════════════════════════
section("Joint Relationships — do the variables move together correctly?",
        "Matching each variable alone is not enough; the correlations between variables must also be right (e.g. older "
        "people earn differently, spouses come in pairs). These slides test exactly that.")

figure("F8 — Joint fidelity by interaction order", FV / "F8_joint_srmse_by_order.png",
   shows="How error grows as we test single variables, then pairs of variables, then triples — i.e. increasingly "
         "demanding joint structure.",
   read="X-axis = interaction order (1-way, 2-way, 3-way); Y-axis = mean SRMSE (lower is better). Three bars that "
        "rise with order — expected and universal: higher-order combinations have fewer samples and are harder to match.",
   numbers=f"Person joints: 1-way {_J1}, 2-way {_J2}, 3-way {_J3}. The hardest pairs are "
           f"age×income ({_wp('age_bin×income_bin')}), occupation×relationship ({_wp('occupation×relationship')}) "
           f"and age×relationship ({_wp('age_bin×relationship')}).",
   formula=[
     ("Standardized RMSE over the cells of an m-way contingency table (generated vs observed counts):",""),
     ("&nbsp;&nbsp;SRMSE = √( (1/K) · Σ<sub>k</sub> (n<sub>gen,k</sub> − n<sub>obs,k</sub>)² ) / n&#772;<sub>obs</sub>",
      "K = number of joint cells; n&#772;<sub>obs</sub> = mean observed cell count. Normalizing by the mean makes it "
      "comparable across tables of different size — hence 'standardized'."),
   ],
   say="Single variables are matched tightly; pairwise and three-way structure degrade gracefully, which is exactly "
       "what you expect. The pairs that lag most all involve within-household coupling — age, income, and role — and "
       "that points at the one known limitation I'll show at the end.")

JOINTS = [
 ("F3 — Age × Income joint", "F3_joint_age_bin_x_income_bin.png",
  "the two-way table of age band against income band",
  f"the hardest pair (SRMSE {_wp('age_bin×income_bin')}): younger vs older people's income profiles"),
 ("F3 — Age × Relationship joint", "F3_joint_age_bin_x_relationship.png",
  "the two-way table of age band against household role",
  "how role depends on age (children young, householders older)"),
 ("F3 — Occupation × Relationship joint", "F3_joint_occupation_x_relationship.png",
  "the two-way table of occupation against household role",
  "how employment status lines up with household role"),
]
for ttl, fn, shows_tail, say_tail in JOINTS:
    figure(ttl, FV / fn,
       shows=f"Three heatmaps side by side for {shows_tail}: truth (test), generated, and their difference.",
       read="Read left→right: the first two panels should look alike; the third (difference) should be near-flat / "
            "near-zero (often near-white). Bright cells in the difference panel are where the joint is off.",
       numbers="The difference panel is close to zero across the table.",
       say=f"This is {say_tail}. The two data panels look the same and the difference panel is essentially blank, so "
           "the joint relationship is reproduced.")

figure("S3 — Association matrix: TRUTH (Cramér's V)", FV / "S3_cramersV_test.png",
   shows="A matrix of the association strength between every pair of categorical variables, computed on the real "
         "(test) data. Cramér's V runs 0 (no association) to 1 (perfect association).",
   read="Rows and columns are the variables; each cell's shade = how strongly that pair is related in reality. This "
        "is the target pattern the generated data must reproduce.",
   numbers="Bright cells mark the genuinely correlated pairs (e.g. age–relationship, income–occupation).",
   formula=[
     ("Cramér's V — association strength for a pair of categorical variables (r×c table, n records):",""),
     ("&nbsp;&nbsp;V = √( χ² / ( n · min(r−1, c−1) ) )",
      "χ² is the Pearson chi-square of the contingency table; V ∈ [0,1], 0 = independent, 1 = perfect association. "
      "The matrices compare V computed on truth vs on generated data."),
   ],
   say="This is the 'correlation fingerprint' of the real population — which variables genuinely move together.")

figure("S3 — Association matrix: GENERATED", FV / "S3_cramersV_generated.png",
   shows="The same association matrix, computed on the generated population.",
   read="Compare shading cell-for-cell against the previous (truth) matrix — the pattern should look the same.",
   numbers="The generated matrix visually matches the truth matrix.",
   say="The generated population shows the same web of associations as the real one — same bright cells, same faint "
       "ones.")

figure("S3 — Association matrix: DIFFERENCE", FV / "S3_cramersV_diff.png",
   shows="Generated minus truth for every pair — an error map of the association structure.",
   read="Near-zero (near-white / neutral) everywhere means the dependencies are preserved. Any strong cell would flag "
        "a mis-modeled relationship.",
   numbers="The difference is near zero across the whole matrix.",
   say="This is the clean summary: the difference is essentially blank, so the pairwise dependency structure is "
       "preserved, not just the individual variables.")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════
# STRUCTURAL ZEROS
# ══════════════════════════════════════════════════════════════════════════
section("Structural Zeros — are all the records physically possible?",
        "A structural zero is a combination that must never occur (a 10-year-old with a driver's license, a retiree "
        "aged 30). Statistical models often emit a few; ours emits none, by construction.")

figure("Z — Structural-zero violations", FV / "Z_structural_zeros.png",
   shows="A tally of forbidden combinations in the generated population across a list of hard rules "
         "(under-16 drivers, under-62 retirees, toddlers over age 5, spouses under 16, out-of-range ages, "
         "households without exactly one householder, etc.).",
   read="Each rule has a count of violations; every bar is zero. Non-zero would mean the model produced impossible "
        "people.",
   numbers="Total violations = 0, across every rule. This is guaranteed by constrained decoding — impossible classes "
           "are masked to probability zero before sampling, so they can never be drawn.",
   say="Every generated record is physically and logically valid — zero impossible combinations. That's not luck; we "
       "mask impossible categories during decoding so they literally cannot be sampled. For a population that feeds a "
       "downstream simulation, this hard guarantee matters.")

# ══════════════════════════════════════════════════════════════════════════
# CLOSING
# ══════════════════════════════════════════════════════════════════════════
section("Closing — the summary slide")
figure("Validation summary table + how to close", None,
   shows="The final table collects the whole story: training fit, latent health, no memorization, marginals, joints, "
         "association, structural zeros, coherence, and the workplace assignment.",
   read=None,
   numbers="Training converges with no overfit; 24/24 latent dims active; only 61% of generated types seen in "
           "training; marginals at/below 0.03 TV; joints 0.06/0.14/0.24 by order; association difference ≈ 0; "
           "structural-zero violations 0; Σ income exact 99.98%; 6.09M jobs assigned with 0 unreachable.",
   say="To close: a simple, transparent VAE produces a fully valid synthetic population that matches the real one on "
       "single variables, on the relationships between variables, and on hard constraints — while demonstrably "
       "generalizing rather than memorizing. The one honest limitation is within-household coupling (e.g. spouse "
       "ages are a bit too spread out); it's bounded, diagnosed, and fixable with a cross-person decoder if a future "
       "use case demands it. The population is ready to drive SILO, MITO, and MATSim.")

# an explicit note about the couple-age-gap limitation, since a reviewer may ask
figure("If asked about limitations (couple age gap)", None,
   shows="The one diagnosed ceiling. Because the person heads are conditionally independent given the latent z, the "
         "model doesn't tightly bind two people's attributes within a household.",
   read=None,
   numbers="The clearest symptom: the age gap between spouses averages ~7.7 years in the generated data vs ~3.7 "
           "years in the test data — couples are a bit too age-dispersed. This also explains why age, income and "
           "relationship are the marginals/joints that lag slightly.",
   say="If someone probes the weak spot, name it plainly: within-household coupling. The single shared latent carries "
       "most correlations but doesn't perfectly pin one person's attributes to another's, so spouse ages spread too "
       "wide. We tried the simple fixes (bigger latent, lower β, deeper decoder) and they didn't help; the real fix "
       "is an autoregressive/cross-person decoder or a light post-hoc calibration, both of which we deliberately kept "
       "out of scope to keep the model simple.")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════
# SILO SECTION
# ══════════════════════════════════════════════════════════════════════════
section("SILO — Land-Use Microsimulation (methods + Maryland validation)",
        "This is the second half of the deck. SILO takes the VAE 2016 population and ages it forward year by year to "
        "2023, then we validate the forecast against ACS. The acceptance test is stricter than the VAE's: not an "
        "overall distance, but a PER-BIN one — every category of every variable must land within ±5 percentage points "
        "of ACS. We show Maryland only.")

figure("SILO in one slide — the pipeline", None,
   shows="The flow: the VAE 2016 synthetic population (households, persons, dwellings, jobs) feeds SILO, which runs an "
         "annual microsimulation from 2016 to 2023; each simulated year emits a full population that is scored against "
         "ACS PUMS 5-year.",
   read="Left-to-right is time / data flow. The key word is 'closed model': nothing is re-seeded from outside — every "
        "person and household is aged forward by the model's own rules, so how well 2021–2023 matches reality is an "
        "honest test of the dynamics.",
   numbers="Region: 6 states (DE, DC, MD, PA, VA, WV) across 96 PUMAs; base year 2016 comes straight from the VAE and "
           "SILO is never re-fit to it.",
   say="SILO is the land-use engine. It starts from our VAE population and simulates each year forward to 2023. "
       "Because it's a closed model — no re-seeding — the forecast years are a genuine out-of-sample test, not a fit.")

figure("SILO — the annual simulation loop (what runs each year)", None,
   shows="Everything that fires in one simulated year, in two groups: micro-event models per person/household (birth, "
         "death, marriage, divorce, education, employment, moves, migration) and annual market-update models "
         "(job-market clearing, real-estate pricing, construction, auto-ownership, income adjustment).",
   read="Read it as two columns: life-events on the left, market updates on the right. Both run every year for every "
        "agent.",
   numbers="Auto-ownership is the model we wired in and self-calibrate; income and the housing/job markets re-clear "
           "annually.",
   formula=[
     ("Every discrete-choice event (auto-ownership, residential moves, marriage, job take-up, …) is a multinomial logit:",""),
     ("&nbsp;&nbsp;P(i) = exp(V<sub>i</sub>) / Σ<sub>j</sub> exp(V<sub>j</sub>)",
      "V<sub>i</sub> = systematic utility of alternative i (e.g. for auto-ownership, i ∈ {0,1,2,3+} cars). "
      "For rate-based life events the annual hazard is scaled by a per-state lever:"),
     ("&nbsp;&nbsp;rate<sub>state</sub> = s<sub>state</sub> · rate<sub>base</sub>",
      "s<sub>state</sub> from calibration_by_state.csv (birth / marriage / income / auto scalers)."),
   ],
   say="Each year, every person can be born, age, marry, move, change jobs; then the markets re-clear — housing gets "
       "re-priced, jobs re-matched, cars and income re-assigned. Run that eight times and you've walked the whole "
       "population from 2016 to 2023.")

figure("SILO — calibration & validation methodology (the core slide)", None,
   shows="The two-row loop. Top row (calibration): run SILO 2016–2020, validate against ACS in-sample, adjust "
         "per-state levers, and iterate until the in-sample fit converges. Bottom row: FREEZE the levers, forecast "
         "2021–2023, and validate out-of-sample.",
   read="The split between the rows is the whole point — the top is where we're allowed to tune; the bottom is a "
        "sealed test where we change nothing.",
   numbers="Acceptance is PER-BIN: every category of every variable within ±5 pp of ACS. Per-state levers: birth, "
           "marriage, income, and an auto-ownership constant that self-calibrates to 2016 then freezes. Plus "
           "composition re-anchoring for race, household-size and income.",
   formula=[
     ("Per-bin acceptance test (the pass/fail bar), for every category k of every variable:",""),
     ("&nbsp;&nbsp;| share<sub>SILO</sub>(k) − share<sub>ACS</sub>(k) | ≤ 5 percentage points",
      "stricter than a single aggregate distance — every cell must pass, not just the average."),
     ("&nbsp;&nbsp;auto ASC self-calibration: fit constants α<sub>c</sub> so P(c cars) matches 2016 ACS, then FREEZE for 2017–2023.",""),
   ],
   say="This is the methodology slide, so slow down here. We calibrate only on 2016–2020, then we FREEZE every lever "
       "and forecast 2021–2023 with no further tuning — so those three years are a true out-of-sample test. Our bar is "
       "deliberately strict: not an average distance, but per-bin — every single category of every variable has to be "
       "within five percentage points of ACS. The levers are per state (birth, marriage, income, car-ownership), and "
       "because migration in a closed model is composition-neutral, we add a light re-anchoring step so race, "
       "household size and income don't drift while the real world moves.")

section("Maryland — Year-to-Year Validation",
        "One summary figure, then one figure per variable for 2023 (the last, hardest out-of-sample year). Remember "
        "the metric on the summary chart is Total Variation, but the pass/fail test is per-bin ±5pp — and Maryland "
        "passes every cell, every year.")

figure("Maryland — the year-to-year summary figure", SVFIG / "md_year_to_year.png",
   shows="One line per variable, tracking the SILO-vs-ACS Total Variation from 2016 to 2023. The shaded region on the "
         "right (2021–2023) is the out-of-sample forecast; the dashed line marks where calibration ends.",
   read="X-axis = year; Y-axis = Total Variation (lower = closer to ACS). Flat, low lines are good. A gentle rise into "
        "the shaded region is expected — that's the forecast drifting slightly as it gets further from the calibrated "
        "base year.",
   numbers="All variables stay low. Age is the highest (~0.06), then occupation, autos and race (~0.02–0.03); gender, "
           "income, household-size and dwelling stay under ~0.015. Nothing blows up in the forecast window.",
   say="This one chart is the Maryland story. Every variable stays close to ACS across all eight years, and even in "
       "the out-of-sample window on the right the lines only tick up gently — no runaway drift. Age sits highest, but "
       "as the next slides show, that's spread thinly across eighteen age bins, so per-bin it's still tiny.")

# per-variable 2023 pages
MDV = [
 ("pp_age_bin.png", "Maryland 2023 — Age",
  "TV 0.064 (Maryland's largest), yet the max per-bin gap is only 1.3 pp — comfortably inside ±5 pp.",
  "Age is the variable to speak to directly, because its TV looks high. The reason is harmless: there are eighteen "
  "five-year age bins, so even a good fit accumulates a bit of Total Variation, but no single bin is off by more than "
  "1.3 points. The only pattern is a mild over-count of 50–69-year-olds and under-count of 25–34 — the signature of a "
  "closed model aging its base population forward. It still passes the ±5pp bar everywhere."),
 ("pp_occ_silo.png", "Maryland 2023 — Occupation",
  "TV 0.031. Reconciled each year by the occupation-update model (non-workers re-classified to toddler/student/"
  "retiree by age and ACS enrollment).",
  "Occupation was one of our bigger fixes: stock SILO graduated every student at 19 and never assigned retirees, so "
  "we added an annual model that re-classifies non-workers by age against ACS. In Maryland it lands well within the bar."),
 ("hh_autos.png", "Maryland 2023 — Autos per Household",
  "TV 0.025. The auto-ownership constants self-calibrate to 2016 shares, then freeze.",
  "Car ownership: the model fits its own constants to the 2016 distribution once, then freezes them, so the forecast "
  "years are honest. Maryland's 0/1/2/3+ shares stay within a couple of points of ACS."),
 ("hh_hhSize.png", "Maryland 2023 — Household Size",
  "TV 0.014. Held flat by the composition re-anchoring step.",
  "Household size is a good example of the re-anchoring at work — without it a closed model freezes the size mix while "
  "ACS shifts toward smaller households; with it, Maryland tracks ACS to within about a point per bin."),
 ("hh_dwellingType.png", "Maryland 2023 — Dwelling Type",
  "TV 0.015. Single-family vs multi-family mix reproduced.",
  "Dwelling type is a housing-stock variable, driven by the construction and demolition models; Maryland's mix stays "
  "close to ACS."),
 ("pp_race4.png", "Maryland 2023 — Race",
  "TV 0.022 (up from 0.007 at the 2016 base — the drift the re-anchor is designed to bound).",
  "Race is where you can see the closed-model drift most clearly: it starts almost perfect in 2016 and slowly diverges "
  "as the population ages without realistic in-migration. The re-anchoring keeps it bounded — 0.022 is still small and "
  "within the ±5pp per-bin bar."),
 ("hh_hh_inc9.png", "Maryland 2023 — Household Income",
  "TV 0.013; median-income bias about +1.0%.",
  "Household income across the nine bins is one of the tightest — the median is within about one percent of ACS, and "
  "the income re-anchoring keeps the whole distribution aligned."),
 ("pp_gender.png", "Maryland 2023 — Gender",
  "TV 0.005 — essentially exact.",
  "Gender is a sanity check — it should be near-perfect and it is, within half a percentage point."),
]
for fn, ttl, num, say in MDV:
    figure(ttl, SMD23 / fn,
       shows="Two panels for Maryland in 2023. Top: ACS (observed) vs SILO (model) shares for each category. Bottom: "
             "the SILO − ACS gap per category, with the green band marking the ±5-percentage-point acceptance zone.",
       read="Read the bottom panel: every bar inside the green band passes. The title also prints the max per-bin gap "
            "and the Total Variation.",
       numbers=num, say=say)

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════
# ABIT SECTION (agent-based, tour-based activity model)
# ══════════════════════════════════════════════════════════════════════════
section("ABIT — Agent-Based Activity Model (tour-based)",
        "The third part of the deck. ABIT is the travel model that turns the population into trips. It is the "
        "operative implementation of the Chayan & Cirillo (2024) SILO→MITO→MATSim suite (Socio-Economic Planning "
        "Sciences 95, 102031), run on the SILO/VAE synthetic population. Its unit of demand is the home-anchored TOUR, "
        "its mode choice is a generalized-cost MNL extended with an income-dependent value of time, and it is built to "
        "feed MATSim and answer the I-695 congestion-pricing question. Everything here is validated against the "
        "Regional Travel Survey (RTS) for Maryland residents.")

figure("ABIT — overview", None,
   shows="The pipeline: the SILO/VAE synthetic population feeds ABIT, which sets each person's daily activity pattern, "
         "draws home-anchored tours, then for every tour chooses destination, mode, stops and schedule, and writes one "
         "chained daily plan per person that goes to MATSim.",
   read="Left-to-right is the flow. The key idea is that the unit is the TOUR — the whole home-to-home chain — so trip "
        "counts come out right by construction instead of being over-generated.",
   numbers="ABIT = the Chayan & Cirillo (2024) tour-based suite. Nine estimated components; mode choice is a "
           "generalized-cost MNL over 7 modes, RTS-calibrated (car-driver ≈ 0.76, i.e. +9.2 pp above RTS 0.67; transit "
           "is calibrated to NTD ridership — a calibration-to-ridership step, not an independent target — because RTS "
           "over-reports transit). Validated vs RTS: 1.37 tours/traveler-day, county productions/attractions/O-D "
           "r² ≈ 0.99.",
   say="ABIT is our activity-based travel model — the operative version of the Chayan and Cirillo tour-based suite, run "
       "on our synthetic population. The unit is the home-anchored tour, so trip counts are right by design. It chains "
       "nine estimated models into one daily plan per person for MATSim. The one extension that matters for policy is "
       "an income-dependent value of time in mode choice, which is what makes the tolling response income-elastic.")

figure("Trip generation by purpose — ABIT vs RTS", ABITF / "fig1_tripgen_purpose.png",
   shows="Tours generated per purpose (work, school, shop, other) by the applied model against the RTS survey.",
   read="Compare the applied bars to the survey bars for each purpose; closer is better. The headline is the total "
        "tour rate.",
   numbers="1.37 tours per traveler-day, equal to the RTS target; per-purpose rates track the survey.",
   formula=[
     ("Tour frequency — number of home-anchored tours of purpose p drawn per traveller n as a rate/Poisson process:",""),
     ("&nbsp;&nbsp;n<sub>tours,p</sub> ~ Poisson(λ<sub>p</sub>(x<sub>n</sub>)),&nbsp;&nbsp;Σ<sub>p</sub> E[n<sub>tours,p</sub>] ≈ 1.37 tours / traveller·day",
      "λ<sub>p</sub> depends on person/household attributes x<sub>n</sub>; the tour is the whole home→…→home chain, so "
      "trip counts come out right by construction (no over-generation)."),
   ],
   say="Trip generation is right: the model produces 1.37 tours per traveler-day, exactly the survey number, and the "
       "split across work, school, shop and other matches the RTS. This is the cure for the old trip-based model's "
       "over-generation.")

figure("Mode share — ABIT vs RTS", ABITF / "fig7_mode_share.png",
   shows="The 7-mode split (auto-driver, auto-passenger, shared-ride, bus, train, walk, bike) from the applied model "
         "against the survey.",
   read="Compare applied vs survey per mode. Note the transit treatment: the NTD ridership figure is a CALIBRATION "
        "target we anchor transit to (it is RTS-boarding-ratio-derived and the ASCs are re-anchored to it), NOT an "
        "independent validation — describe it as calibration-to-ridership, not 'validated against NTD'.",
   numbers="Car-driver ≈ 0.76 in ABIT vs ≈ 0.67 in RTS — i.e. +9.2 pp ABOVE the survey, a consequence of the transit "
           "re-anchoring (RTS over-reports transit, so transit is calibrated down to NTD ridership and the car share "
           "absorbs the difference). Transit share is calibration-to-ridership, not an independent target.",
   formula=[
     ("Mode choice is a multinomial logit over the 7 modes (see the Formulation slide for the full income-VOT spec):",""),
     ("&nbsp;&nbsp;P<sub>n,m</sub> = exp(U<sub>n,m</sub>) / Σ<sub>j</sub> exp(U<sub>n,j</sub>)",
      "U<sub>n,m</sub> = ASC<sub>m</sub> + β<super>T</super>x<sub>n</sub> + β<sub>GC</sub>·GC<sub>n,m</sub>; ASCs calibrated to RTS."),
   ],
   say="Mode shares reproduce the region's structure: car-dominated, with transit and active modes at small shares. Be "
       "precise and honest here. Our car-driver share is about 76 percent, which is roughly 9 points ABOVE the RTS "
       "survey's 67 percent — that gap is not error, it is the transit re-anchoring: the survey over-reports transit, "
       "so we calibrate transit down to National Transit Database ridership and the car share picks up the difference. "
       "And say it plainly — the NTD figure is a calibration-to-ridership target, not an independent validation.")

figure("Income-dependent value of time — the equity engine", ABITF / "fig7_mode_share.png",
   shows="The mechanism that makes tolling income-elastic. Mode choice is a generalized-cost MNL whose cost term is "
         "divided by an income-scaled value of time, VOT·(income/median)^0.6. (Shown alongside the mode-share figure "
         "because it is the same model.)",
   read="Think of three travellers. A low-income traveller has a low value of time, so the cost part of the utility "
        "dominates and a toll deters them most. A high-income traveller has a high value of time, so they value the "
        "time saving and keep driving / pay. The median traveller is the reference.",
   numbers="Cost coefficient scales as VOT·(income/median)^0.6. Base 7-mode shares stay RTS-calibrated, so today's "
           "split is reproduced while the model still responds correctly to price.",
   formula=[
     ("Cost enters utility as generalized cost, with the money term divided by an income-scaled value of time:",""),
     ("&nbsp;&nbsp;GC<sub>n,m</sub> = t<sub>n,m</sub> + 60 · c<sub>n,m</sub> / VOT<sub>m</sub>(I<sub>n</sub>)",
      "t in minutes; c in dollars; the ×60 converts $/h VOT into a per-minute basis so GC is in time units."),
     ("&nbsp;&nbsp;VOT<sub>m</sub>(I<sub>n</sub>) = VOT<sub>m</sub><super>ref</super> · (I<sub>n</sub> / I<sub>ref</sub>)<super>0.6</super>",
      "lower income → lower VOT → the same dollar toll is a LARGER disutility → larger mode shift. That is the equity engine."),
   ],
   say="This is the slide that makes the model answer the equity question. The cost of driving is divided by an "
       "income-scaled value of time. A toll raises the generalized cost of driving; because lower-income travellers "
       "have a lower value of time, the same toll deters them more, so they shift to transit and other modes at higher "
       "rates. That means we can report welfare incidence by income and race, not just an aggregate diversion number — "
       "and it falls straight out of one transparent term.")

figure("Income-dependent VOT mode choice — formulation", MATF.parent.parent / "docs" / "income_vot_modechoice_slide.png",
   shows="The formal statement of the equity mechanism: four equations plus a VOT-factor-vs-income curve and an "
         "equity-mechanism box. (1) the multinomial-logit choice probability over the 7 modes; (2) the mode utility "
         "V = ASC + β_cost·GC + demographics; (3) the generalized cost GC = in-vehicle time + (toll + fare + operating "
         "cost)/VOT; and (4) the continuous, income-dependent value of time, VOT_h = VOT_ref·(income_h/median)^0.6.",
   read="Read from the bottom equation up. Each household h gets its OWN value of time from its income (the curve on "
        "the right). That VOT sits in the denominator of the money terms in the generalized cost, so a fixed toll in "
        "dollars converts into MORE utility-cost for a low-income agent (small VOT) than for a high-income agent "
        "(large VOT). Feed that GC into the utility and then the logit, and the toll produces a larger mode shift for "
        "lower-income travellers.",
   numbers="Continuous per-agent VOT with exponent 0.6 on (income/median); the money terms (toll + fare + operating "
           "cost) are divided by VOT_h; a fixed toll therefore has a larger disutility for lower-income agents. Base "
           "7-mode shares stay RTS-calibrated, so today's split is reproduced while the response to price is "
           "income-elastic.",
   formula=[
     ("Chayan &amp; Cirillo (2024) income-dependent VOT mode choice — the four equations on the slide:",""),
     ("&nbsp;&nbsp;(1)&nbsp; P<sub>n,m</sub> = exp(U<sub>n,m</sub>) / Σ<sub>j</sub> exp(U<sub>n,j</sub>)",
      "multinomial-logit choice probability over the 7 modes for traveller n."),
     ("&nbsp;&nbsp;(2)&nbsp; U<sub>n,m</sub> = ASC<sub>m</sub> + β<super>T</super> x<sub>n</sub> + β<sub>GC</sub> · GC<sub>n,m</sub>",
      "mode utility: alternative-specific constant + demographic terms + generalized-cost term."),
     ("&nbsp;&nbsp;(3)&nbsp; GC<sub>n,m</sub> = t<sub>n,m</sub> + 60 · c<sub>n,m</sub> / VOT<sub>m</sub>(I<sub>n</sub>)",
      "generalized cost = in-vehicle time + money terms (toll + fare + operating cost) converted to minutes via VOT."),
     ("&nbsp;&nbsp;(4)&nbsp; VOT<sub>m</sub>(I<sub>n</sub>) = VOT<sub>m</sub><super>ref</super> · clip[ (I<sub>n</sub> / I<sub>ref</sub>)<super>λ</super>, 0.4, 2.5 ]",
      "continuous per-agent VOT, clipped to [0.4×, 2.5×]. I<sub>ref</sub> = $7,018/mo, λ = 0.6; "
      "VOT<sup>ref</sup> = car 30 / shared-ride 40 / transit 15 $/h."),
   ],
   say="This is the formulation behind the equity claim, in four equations. The bottom one is the key: value of time "
       "is continuous and scales with each household's income, so everyone has their own VOT. That VOT divides the "
       "money terms — toll, fare, operating cost — in the generalized cost, which then enters the utility and the "
       "seven-mode logit. The consequence is mechanical: the same dollar toll costs a low-income agent more utility "
       "than a high-income agent, so lower-income travellers shift mode more. The base shares stay calibrated to the "
       "survey, so we reproduce today's split and still get an income-elastic toll response — no extra assumptions.")

figure("Spatial validation — county productions / attractions / O-D", ABITF / "fig2_prod_attr_county.png",
   shows="The applied model against RTS at the county level: trip productions, trip attractions, and origin-destination "
         "flows.",
   read="Each panel is a scatter of applied vs survey, one point per county (or O-D pair); points on the 45-degree line "
        "mean a perfect match. Look at the r².",
   numbers="Productions, attractions and O-D flows all validate at r² ≈ 0.99.",
   say="Spatially the model is excellent — county productions, attractions and origin-destination flows all line up "
       "with the survey at an r-squared of about 0.99. So it's not just the totals that are right; trips are in the "
       "right places.")

figure("County-level distribution — ABIT vs RTS", ABITF / "fig5_county_bars.png",
   shows="A two-panel bar chart: trip productions by home county (top) and attractions by destination county "
         "(bottom), applied ABIT vs the RTS survey, for the Maryland counties (a star marks the Baltimore "
         "Metropolitan Region study-area counties).",
   read="Read it county by county — for each county compare the applied bar against the survey bar, in both the "
        "productions panel and the attractions panel; matching heights mean the geography is right.",
   numbers="ABIT tracks RTS across all counties in both productions and attractions; the BMR study-area counties "
           "(starred) carry the bulk of the trips and line up closely — the county-level view behind the r² ≈ 0.99 "
           "scatter.",
   say="This is the same spatial result as the scatter, but broken out county by county so you can see it directly. "
       "The applied bars sit on top of the survey bars for productions and for attractions, across every Maryland "
       "county, with the Baltimore-region counties — the starred ones — carrying most of the trips and matching "
       "closely. It's the concrete picture behind the 0.99 r-squared.")

figure("Activity location assignment — POI / facility-based", None,
   shows="How each non-home activity gets its exact coordinate. Instead of dropping the activity at the zone centroid "
         "(or a random point in the zone, as in published SILO), every activity is placed on a REAL OpenStreetMap "
         "facility of its own category, inside the chosen zone.",
   read="Read the category matching as the key idea: WORK goes to an office/commercial POI, SHOPPING to retail, OTHER "
        "to amenity/services, RECREATION to a leisure/park POI, ACCOMPANY to a school, and a work-based SUBTOUR to an "
        "amenity near the work anchor. This refines location WITHIN a zone, so it does not change any zone-level "
        "validation.",
   numbers="A 609,434-POI index built from a six-state OpenStreetMap extract, covering 1,587 of 1,588 zones. Result: "
           "100% of non-home activities land on a real POI, and degenerate stop-collisions drop from 36% to 1.8%. "
           "Trip-generation, spatial and mode validation are unchanged because they are all zone-level.",
   formula=[
     ("Within the chosen destination zone, the activity coordinate is drawn by a category-matched fallback chain:",""),
     ("&nbsp;&nbsp;loc ← category-matched POI  →  any POI in zone  →  random point in zone  →  zone centroid",
      "each arrow is used only if the previous set is empty; matching maps WORK→office/commercial, SHOP→retail, "
      "RECREATION→leisure/park, ACCOMPANY→school, etc. This refines location WITHIN a zone, so zone-level validation is unchanged."),
   ],
   say="This is a refinement to where activities actually happen. Published SILO drops each activity at a random point "
       "in its zone; we instead place it on a real OpenStreetMap facility of the right category — work at an office, "
       "shopping at retail, recreation at a park, accompany at a school. We built a 609,000-POI index across the six "
       "states covering essentially every zone, so 100% of non-home activities now sit on a genuine facility and "
       "degenerate collisions fall from 36% to under 2%. Nothing in the earlier validation moves, because that's all "
       "zone-level — this just sharpens the within-zone location, which matters for loading the local roads in MATSim.")

figure("Activity locations by category — BMR (7 activity types)", ABITF.parent.parent / "figures_poi" / "fig_bmr_poi_montage.png",
   shows="A 4×2 montage of the Baltimore Metropolitan Region, one map per activity type — home, work, shopping, other, "
         "recreation, accompany, subtour — with county boundaries drawn on each.",
   read="Read each small map for its spatial signature: work concentrates in the CBD, shopping at retail centers, "
        "recreation at parks, accompany at schools. Each dot is a category-matched real facility in one of the six "
        "BMR counties.",
   numbers="Seven activity types placed on category-matched OSM facilities across the six BMR counties; each type "
           "shows a distinct, sensible geographic pattern.",
   say="This montage makes the facility-based placement visible. Each activity type lands on the right kind of real "
       "place and shows its own geography — work clusters downtown, shopping at retail centers, recreation at parks, "
       "the school drop-offs at schools. That's the spatial realism the POI assignment buys us for the network model.")

figure("Trip length by purpose — ABIT vs RTS", ABITF / "fig_triplength_distribution.png",
   shows="Primary-activity distance distributions by purpose (work, shop, other), applied vs survey.",
   read="Compare the applied outline to the survey histogram for each purpose; the MEAN (which drives VMT/AADT) is the "
        "headline, and the median is reported alongside it.",
   numbers="Read from the authoritative v8-plan table (validation_triplength.csv). The MEANS validate within ±13% "
           "(both capped and uncapped): work 12.96 mi vs RTS 13.87 (−6.6%), shop 6.62 vs 5.90 (+12.2%), other 7.88 vs "
           "7.51 (+4.9%), all 8.82 vs 8.97 (−1.7%). Be honest about the residual: the discretionary MEDIANS run above "
           "RTS (shop 4.78 vs 3.15, other 5.92 vs 3.89) because zone-granularity placement leaves ABIT with fewer "
           "sub-zonal short discretionary trips than the survey self-reports — disclosed, not hidden; work's median "
           "validates (9.33 vs 10.02). One disclosed distance rule: inter-zonal trips, crow-fly × 1.3 from the plan "
           "coordinates, uncapped (<200 mi) with a capped (≤60 mi) variant reported. This retires the contradictory v7 "
           "text (−33 to −46% FAIL / 'RESOLVED via uncapped 8.07'): v8 fixed the level at source via the relaxed "
           "destination-choice deterrence shown below.",
   formula=[
     ("Destination choice — each tour's primary zone d is a logit over a travel-time deterrence (dest_friction_power.csv):",""),
     ("&nbsp;&nbsp;V<sub>d</sub> = b<sub>time</sub> · t<sub>od</sub> + b<sub>logtime</sub> · ln(t<sub>od</sub>) + size<sub>d</sub>",
      "size<sub>d</sub> = log attraction (opportunities) of zone d; the two time terms are the impedance."),
     ("&nbsp;&nbsp;P(d) = exp(V<sub>d</sub>) / Σ<sub>d'</sub> exp(V<sub>d'</sub>)",
      "v8 relaxed b<sub>time</sub> / b<sub>logtime</sub> (weaker deterrence) to lengthen trips toward the survey distances shown here."),
   ],
   say="State the trip-length result precisely. The MEAN trip length — the quantity that drives VMT and network "
       "loading — validates within about 13 percent for every purpose, so the aggregate demand travels the right total "
       "distance. Be candid about the one residual: the median discretionary trip (shop, other) comes out longer than "
       "the survey, because we place activities at zone granularity and so generate fewer very-short sub-zonal trips "
       "than people self-report; the work median matches. That is a disclosed limitation of within-zone placement, not "
       "a hidden failure — and it retires the earlier contradictory v7 trip-length numbers.")

figure("Tour rate & time-of-day — ABIT vs RTS", ABITS / "fig_a_tour_rate.png",
   shows="The tour rate (tours per traveler-day) against RTS, the headline generation validation; the model also "
         "reproduces the two-peak time-of-day schedule.",
   read="Compare applied vs survey. The single number to remember is the tour rate; the schedule check is the classic "
        "AM-out / PM-return double peak.",
   numbers="1.37 tours/traveler-day = RTS; the AM-outbound and PM-return commute peaks are both reproduced.",
   say="Two things close the ABIT story. The tour rate is 1.37 per traveler-day, exactly the survey, and the timing "
       "reproduces the familiar morning-out, evening-back double peak — which is what MATSim needs to build "
       "congestion.")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════
# MATSim — I-695 CONGESTION-PRICING SECTION
# ══════════════════════════════════════════════════════════════════════════
section("MATSim — I-695 Congestion-Pricing Study",
        "The final part of the deck. We take the resident 2023 demand (VAE → SILO → ABIT) onto a corrected "
        "facility-standard-speed network and run a hybrid feedback loop to study tolling the I-695 Baltimore Beltway. "
        "The framing to keep honest: this is a resident-only model, so freeway counts under-predict by a documented "
        "through-traffic and commercial scope — that is a scope choice, not an error.")

figure("MATSim / I-695 — pipeline & feedback loop", MATF.parent.parent / "docs" / "pipeline_feedback_diagram.png",
   shows="The concept/algorithm diagram for the whole study: the VAE → SILO → ABIT ⇄ MATSim flow, the ABIT↔MATSim "
         "feedback loop, the outer-loop / inner-loop distinction, and the 5-step feedback algorithm (steps 0–4) with "
         "its outputs. An 'Inside ABIT' zoom shows the model chain — Tour frequency → Destination choice → Mode choice "
         "→ Stops & subtours → Schedule/TOD (7-mode generalized-cost choice, income-dependent VOT, real-POI activity "
         "locations, calibrated to RTS). Note the attribution in the diagram: Chayan & Cirillo (2024) is credited to "
         "the MODE-CHOICE model specifically, not to the activity model as a whole. (This is the concept figure; the "
         "later Hybrid Feedback Loop slide shows the convergence RESULT.)",
   read="Follow the two coloured arrows of the loop: PURPLE carries plans + the mode split (from ABIT's income-VOT "
        "mode choice) INTO MATSim; TEAL carries the congested + tolled skims BACK to ABIT. The OUTER loop is ABIT "
        "mode choice re-solved on those skims (modes can change); the INNER loop is MATSim ReRoute + departure-time "
        "with modes held fixed, iterated to a network equilibrium. The toll enters both — RoadPricing in routing and "
        "the income-VOT term in mode choice.",
   numbers="I-695 Baltimore Beltway; base year 2023; resident-only demand; corrected facility-standard-speed network. "
           "The 5-step algorithm: (0) VAE→SILO→ABIT build the resident plans + initial mode split; (1) MATSim runs the "
           "INNER loop — ReRoute + departure-time to equilibrium on the tolled network; (2) MATSim returns congested + "
           "tolled zone-to-zone skims; (3) ABIT re-runs income-VOT mode choice on those skims (the OUTER loop), "
           "shifting the mode split income-elastically; (4) repeat 1–3 until the mode split converges → outputs "
           "(flows/AADT, mode shift by income, revenue, welfare incidence).",
   formula=[
     ("Inner loop — MATSim scores each plan with the Charypar–Nagel utility and selects plans by logit:",""),
     ("&nbsp;&nbsp;S<sub>plan</sub> = Σ<sub>act</sub> S<sub>act</sub> + Σ<sub>leg</sub> S<sub>travel</sub>",""),
     ("&nbsp;&nbsp;S<sub>act</sub> = β<sub>dur</sub> · t* · ln(t / t<sub>0</sub>),&nbsp;&nbsp; "
      "S<sub>travel</sub> = β<sub>travel</sub> · t<sub>travel</sub> + β<sub>money</sub> · (cost + toll)",
      "t = activity duration, t* = typical duration; RoadPricing adds ΔS = β<sub>money</sub> · τ on each tolled link (toll τ)."),
     ("&nbsp;&nbsp;plan selection: multinomial logit / ChangeExpBeta,&nbsp; P(plan) ∝ exp(S<sub>plan</sub>)",""),
   ],
   say="This one diagram carries the whole study. Read it as a loop: the purple arrow sends the plans and the mode "
       "split from ABIT into MATSim, and the teal arrow sends the congested, tolled skims back to ABIT. The inner "
       "loop is MATSim re-routing and re-timing with modes fixed, to equilibrium; the outer loop is ABIT's income-VOT "
       "mode choice re-solved on those skims, so people can switch mode. The algorithm is five steps: build the "
       "resident demand, run MATSim to equilibrium on the tolled network, return the congested skims, re-run mode "
       "choice on them, and repeat until the mode split stops moving — at which point we read off flows, the "
       "income-elastic mode shift, revenue and welfare. The toll lives in both loops, which is what makes the answer "
       "income-elastic. The later slide shows this loop actually converging.")

figure("The network — facility-standard speeds", MATF / "network_audit" / "network_roadtype_full.png",
   shows="The 2023 network coloured by road type, with free-flow speeds set to facility standards.",
   read="This is the corrected network. The earlier OSRM/Tiwari speed calibration over-slowed freeways (double-counting "
        "node delay); here freeway free-flow speeds are set to facility standards so the assignment starts from the "
        "right speeds.",
   numbers="Free-flow speeds by facility standard; corrects the earlier speed-cal that pulled freeways from ~55 to "
           "~47 mph.",
   say="The network underneath matters. An earlier speed calibration accidentally over-slowed the freeways, so we "
       "reverted to facility-standard free-flow speeds. This corrected network is what the assignment runs on.")

figure("Hybrid feedback loop — convergence (supplementary result; not a numbered deck slide)",
   MATF / "convergence" / "fig0_feedback_architecture_convergence_combined.png",
   shows="The architecture of the hybrid loop and its convergence: the outer ABIT mode-choice layer wrapped around the "
         "inner MATSim route/departure-time layer, plus the convergence trace.",
   read="Read the architecture panel as two nested boxes — outer mode choice, inner route/time — and the convergence "
        "panel as the metric flattening out as the loop settles to equilibrium.",
   numbers="OUTER = ABIT income-VOT mode choice on tolled + congested skims; INNER = MATSim ReRoute + departure-time, "
           "modes fixed; the loop converges.",
   say="This is the engine of the policy analysis. The outer loop lets mode shares respond to the toll on the "
       "congested skims; the inner loop finds the route-and-time equilibrium for those fixed modes. We iterate the two "
       "until both settle, and this figure shows that convergence.")

story.append(PageBreak())

# ── AADT — Simulated vs Observed (deck slides 55–58) ─────────────────────────
# metrics come verbatim from the v7 route/speed-tier CSV so the guide stays in sync.
import csv as _csv
_V7CSV = V7BYROUTE / "route_validation_summary.csv"
def _v7_rows():
    d = {}
    with open(_V7CSV, newline="") as f:
        for r in _csv.DictReader(f):
            d[(r["level"], r["route"])] = r
    return d
_V7 = _v7_rows()
def _band(r):
    b = r["fac_band_pct"]
    return "within band" if b in ("-1", "-1.0") else f"within ±{b}% band"
def _metrics(r):  # pre-escape < and > for reportlab
    return (f"n={r['n']} · corr²(&gt;0)={r['corr2_simpos']} · true R²={r['R2_true']} · "
            f"GEH&lt;5={r['GEH_lt5_pct']}% · {_band(r)}={r['within_facband_pct']}% · "
            f"median bias={r['median_bias_pct']}% · median ratio={r['median_ratio']}")

section("AADT — Simulated vs Observed (deck slides 55–58)",
        "The MATSim network validation: modelled 2023 AADT against MDOT SHA counts. Demand is RESIDENT-ONLY, run on a "
        "10% sample scaled ×10, passenger-car counts. The honest framing for every panel here: resident-scope arterials "
        "VALIDATE; high-through freeways and the finest collectors under-count by a documented scope (through + "
        "commercial traffic, and sparse 10%-sample assignment) — a scope choice, not a model error.")

figure("Overall — all count stations pooled (slide 56)", V7 / "all_stations_sim_vs_obs.png",
   shows="Every non-ramp count station pooled into one modelled-vs-observed AADT scatter, with a single ±50% "
         "(0.5×–1.5×) reference band; the I-695 Beltway stations are circled.",
   read="Points on the 45° line match the count; inside the band is a daily-AADT pass. Read the cloud of arterial "
        "points hugging the line and the freeway points sitting below it (the resident-scope under-count).",
   numbers="Pooled mainline (ALL): corr² ≈ 0.80, GEH&lt;5 ≈ 8.5%, median bias ≈ −21%, median ratio ≈ 0.74 over "
           "~2,000 stations — arterials on the line, freeways low.",
   formula=[
     ("Per-station validation metrics (M = modelled, C = observed count):",""),
     ("&nbsp;&nbsp;GEH = √( 2(M − C)² / (M + C) )",
      "GEH&lt;5 is a strict HOURLY threshold; here it is applied to DAILY AADT, so read it together with the facility band."),
     ("&nbsp;&nbsp;R² = 1 − SSE/SST,&nbsp;&nbsp; %RMSE = 100 · √( Σ(M − C)² / n ) / mean(C),&nbsp;&nbsp; bias = (M − C) / C","",),
     ("&nbsp;&nbsp;NCHRP facility bands: freeway ±7% · principal arterial ±10% · minor arterial ±15% · collector ±25%",
      "a per-station pass = falling inside its facility's band."),
   ],
   say="This is the pooled headline. Arterials sit on the line; freeways come in low by design. State the metrics as a "
       "family — GEH, R², %RMSE and bias — and stress that GEH<5 is really an hourly test, so on daily AADT we read it "
       "alongside the NCHRP facility band rather than on its own.")

figure("Regional inflow / outflow — gateway station selection (slide 57)", None,
   shows="Why and how we check regional in/out flow with a RADIAL SCREENLINE of count stations on the corridors that "
         "carry it, instead of trusting absolute link volumes (which run low under resident-only demand).",
   read="No plot — this is the selection logic. 14 gateways, one clean count per principal radial approach, spread "
        "across compass directions, each with a clean station→link match.",
   numbers="14 gateways: I-95 (SW &amp; NE), I-83 (N), I-70 (W), US-40 (W &amp; E), MD-295 (S), I-795 (NW), I-97 (S), "
           "MD-140 (NW), MD-26 (W), MD-2 (S), MD-43 (NE), MD-144 (W). Radial-screenline result: Σsim 707,520 vs "
           "Σobs 1,158,111 = −38.9% — the resident-scope deficit band. This is a directional consistency check, NOT a "
           "closed cordon; one near-total miss (B0988, I-95 NE) drags the sum.",
   say="Explain the gateway idea: because we carry no through-traffic, absolute freeway volumes are low, so we test "
       "regional in/out flow on a radial screenline of clean gateway counts instead. The sum comes in about 39% low — "
       "exactly the resident-only band — and it's a directional check, not a mass-balance cordon.")

figure("Radial inflow/outflow gateways — network + county map (slide 58)", V7 / "gateway_stations_map.png",
   shows="The MATSim road network (freeways emphasized) with county boundaries, and the 14 radial gateways drawn as red "
         "stars labelled by route and approach.",
   read="A geographic map: position = position on the ground. Each red star is one gateway count on a principal radial "
        "into/out of the region; the emphasized lines are the freeway skeleton.",
   numbers="14 radial gateways across the compass approaches; used for the −38.9% screenline check on the prior slide.",
   say="This map just locates the fourteen gateways from the previous slide — one clean count on each principal radial "
       "approach, spread around the region so the screenline samples every direction of regional travel.")

# ── Design-Speed-Tier Panels (deck slides 59–64) ─────────────────────────────
section("Design-Speed-Tier Panels (deck slides 59–64)",
        "AADT validation sliced by the link's design speed, coarsest cut of the hierarchy. Each panel is modelled vs "
        "observed for one speed tier, with the facility band appropriate to that tier. The pattern to narrate: "
        "resident-dominated commuter tiers (major/arterial) validate; the high-speed freeway tier and the low-speed "
        "local tier under-count for the two documented scope reasons.")
SPEEDTIERS = [
 ("Freeway", "speedtier_Freeway.png", "Design speed — Freeway (≥55 mph) (slide 60)",
  "The high-design-speed tier: carries the most through / non-resident passenger traffic, so the resident-only demand "
  "under-counts it (median ratio 0.71). DIAGNOSTIC scope, not error."),
 ("Major Arterial", "speedtier_MajorArterial.png", "Design speed — Major Arterial (45–55 mph) (slide 61)",
  "Resident-dominated commuter arterials — this tier VALIDATES: median bias −4.6%, median ratio 0.95."),
 ("Arterial", "speedtier_Arterial.png", "Design speed — Arterial (35–45 mph) (slide 62)",
  "Resident-dominated arterials — VALIDATES: median bias −4.2%, median ratio 0.96."),
 ("Collector", "speedtier_Collector.png", "Design speed — Collector (25–35 mph) (slide 63)",
  "Fine links where the 10% sample thins — a moderate under-count (median ratio 0.83); largely a sample-density effect."),
 ("Local Street", "speedtier_LocalStreet.png", "Design speed — Local Street (<25 mph) (slide 64)",
  "Lowest design speed: sparse 10%-sample assignment on the finest links → the largest tier under-count "
  "(median ratio 0.67). DIAGNOSTIC scope."),
]
for _key, _fn, _ttl, _say in SPEEDTIERS:
    _r = _V7[("speed_tier", _key)]
    figure(_ttl, V7SPEED / _fn,
       shows=f"Modelled vs observed 2023 AADT for the {_key} design-speed tier ({_r['speed_band']}), against MDOT SHA counts.",
       read="Points near the 45° line match; read the median ratio and the facility band rather than the strict hourly "
            "GEH for a daily-AADT verdict.",
       numbers=_metrics(_r) + f" · mean speed {_r['mean_mph']} mph · scope: {_r['scope']}",
       say=_say)

# ── Per-Route Panels (deck slides 65–89) ─────────────────────────────────────
section("Per-Route Panels (deck slides 65–89)",
        "AADT validation for each named interstate, US route and major MD arterial (deck order), then the two pooled "
        "facility classes. Same verdict logic: interstates/freeways are DIAGNOSTIC (through + commercial scope); "
        "principal and minor arterials VALIDATE. Numbers below are read verbatim from the route-validation CSV.")
ROUTES = [
 ("I-95", "aadt_I95.png", "I-95", "Interstate", "diagnostic"),
 ("I-695", "aadt_I695.png", "I-695 Baltimore Beltway", "Interstate", "diagnostic"),
 ("I-83", "aadt_I83.png", "I-83 Jones Falls Expwy", "Interstate", "diagnostic"),
 ("I-70", "aadt_I70.png", "I-70", "Interstate", "diagnostic"),
 ("I-895", "aadt_I895.png", "I-895 Harbor Tunnel Thruway", "Interstate", "diagnostic"),
 ("I-97", "aadt_I97.png", "I-97", "Interstate", "diagnostic"),
 ("I-795", "aadt_I795.png", "I-795 Northwest Expwy", "Interstate", "diagnostic"),
 ("MD-295", "aadt_MD295.png", "MD-295 Baltimore-Washington Pkwy", "Freeway", "diagnostic"),
 ("US-1", "aadt_US1.png", "US-1", "Principal Arterial", "validates"),
 ("US-40", "aadt_US40.png", "US-40 Pulaski Hwy", "Principal Arterial", "validates"),
 ("MD-2", "aadt_MD2.png", "MD-2 Ritchie Hwy", "Principal Arterial", "validates"),
 ("MD-140", "aadt_MD140.png", "MD-140 Reisterstown Rd", "Principal Arterial", "validates"),
 ("MD-45", "aadt_MD45.png", "MD-45 York Rd", "Principal Arterial", "validates"),
 ("MD-144", "aadt_MD144.png", "MD-144 Frederick Rd", "Principal Arterial", "validates"),
 ("MD-26", "aadt_MD26.png", "MD-26 Liberty Rd", "Principal Arterial", "validates"),
 ("MD-170", "aadt_MD170.png", "MD-170 Camp Meade Rd", "Principal Arterial", "validates"),
 ("MD-139", "aadt_MD139.png", "MD-139 Charles St", "Principal Arterial", "validates"),
 ("MD-25", "aadt_MD25.png", "MD-25 Falls Rd", "Minor Arterial", "validates"),
 ("MD-648", "aadt_MD648.png", "MD-648 Baltimore-Annapolis Blvd", "Minor Arterial", "validates"),
 ("MD-3", "aadt_MD3.png", "MD-3 Crain Hwy", "Minor Arterial", "validates"),
 ("MD-175", "aadt_MD175.png", "MD-175 Annapolis Rd", "Minor Arterial", "validates"),
 ("MD-97", "aadt_MD97.png", "MD-97 Georgia Ave", "Minor Arterial", "validates"),
 ("Minor Arterial (all)", "aadt_MinorArterial(all).png", "Minor Arterial — pooled", "Minor Arterial", "validates"),
 ("Collector-Local (all)", "aadt_CollectorLocal(all).png", "Collector / Local — pooled", "Collector / Local", "diagnostic"),
]
for _key, _fn, _disp, _cls, _tag in ROUTES:
    _r = _V7[("route", _key)]
    if _tag == "validates":
        _verdict = "This resident-scope facility VALIDATES."
    else:
        _verdict = ("DIAGNOSTIC scope — the under-count is the documented through + commercial (freeway) or sparse "
                    "10%-sample (collector/local) scope, not a model error.")
    figure(f"{_disp} — {_cls} [{_tag}] (slide reflects deck 66–89)",
       V7BYROUTE / _fn,
       shows=f"Modelled vs observed 2023 AADT along {_disp}, a {_cls.lower()}, against MDOT SHA counts.",
       read="Points near the 45° line match the count; read the median ratio / bias and the facility band for a "
            "daily-AADT verdict rather than the strict hourly GEH.",
       numbers=_metrics(_r) + f" · scope: {_r['scope']}",
       say=f"{_disp}. {_verdict} corr²(&gt;0) {_r['corr2_simpos']}, true R² {_r['R2_true']}, GEH&lt;5 "
           f"{_r['GEH_lt5_pct']}%, {_band(_r)} {_r['within_facband_pct']}%, median ratio {_r['median_ratio']}, "
           f"over n={_r['n']} stations.")

figure("Toll scenario — upcoming (supplementary; the pipeline's next deliverable)", None,
   shows="What comes next: the priced scenario and its equity results. The base case is running now; the toll run is "
         "the next deliverable.",
   read=None,
   numbers="Base case: resident 2023 demand, calibrated facility-standard network, hybrid loop converged. Scenario: "
           "apply the I-695 toll (RoadPricing + income-VOT cost) and re-run the hybrid loop. Pending outputs: mode "
           "shift by income, toll revenue, and consumer-surplus / welfare change by income and race.",
   say="The base case is running now, and the next step is the toll scenario — apply the I-695 "
       "price and re-solve the hybrid loop. Because the value of time is income-scaled, the mode response is "
       "income-elastic by construction, so we'll be able to report not just diversion and revenue but the welfare "
       "incidence by income and race — the equity result the whole pipeline was built to produce.")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════
# I-95 CORRIDOR TRAJECTORY ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
story.append(PageBreak())
I95 = ROOT.parent / "Updated MATSim" / "i95_analysis"
def _i95(name):
    t = I95 / (name + "_trim.png")
    return t if t.exists() else I95 / (name + ".png")
section("I-95 Corridor Trajectory Analysis",
        "Before pricing, we characterise WHO uses the I-95 corridor and HOW it operates, from the base MATSim run. "
        "Corridor users = the 26,967 agents (~270,000 scaled ×10) whose vehicle traverses at least one of the 597 "
        "I-95 mainline links. This is the equity + operations baseline the toll scenario is measured against.")

figure("I-95 corridor — network links by carriageway", _i95("a1_i95_corridor_map"),
   shows="The 597 I-95 mainline network links that define 'the corridor', drawn over the six BMR county boundaries, "
         "split by travel direction (northbound vs southbound carriageway).",
   read="This is a geographic map, not a data plot: the x-axis is Easting and the y-axis is Northing in metres "
        "(projected CRS EPSG:26985) — position on the page = position on the ground. Colour distinguishes the two "
        "one-way carriageways (the divided freeway is two separate link sets); the thin grey polygons are county lines.",
   numbers="597 I-95 links; corridor length ≈ 93 km through the Baltimore region; NB and SB carriageways matched as a pair.",
   say="This is the spatial definition of the corridor — every trajectory, flow and user figure that follows is built "
       "only from vehicles that touch one of these links, so it fixes exactly what 'an I-95 user' means.")

figure("I-95 users — route density", _i95("a2_i95_user_route_density"),
   shows="Where I-95 corridor users come from and go to — the spatial density of their trips across the region.",
   read="Geographic map (Easting × Northing, metres). Brightness/colour intensity = how many corridor-user trips pass "
        "through or end at each area (darker = denser); the I-95 spine is drawn on top in high contrast so you can see "
        "demand feeding onto the corridor.",
   numbers="26,967 corridor users (~270k scaled). Densest around the Baltimore core and the northern/western suburbs.",
   say="I-95 draws users from across the whole metro, not just adjacent neighbourhoods — the corridor is regional. That "
       "matters for pricing: a toll here touches trips originating well beyond the immediate corridor.")

figure("I-95 users — origin–destination desire lines", _i95("a3_i95_user_desire_lines"),
   shows="Straight origin→destination 'desire lines' for I-95 corridor users, coloured by the traveller's home county.",
   read="Geographic map. Each thin line joins one trip's origin to its destination (a straight desire line, not the "
        "driven route); the colour = home county (an 8-colour qualitative palette). Green dots mark origins (home), red "
        "dots mark the primary destinations. Long radial lines = long regional trips.",
   numbers="Top home counties: Baltimore Co., Howard, Baltimore City, Harford, Anne Arundel.",
   say="The fan of long radial desire lines confirms I-95 users are regional commuters from the northern/western "
       "suburbs into the core — the classic corridor commute the toll is designed to influence.")

figure("I-95 time–space diagrams (NB/SB × AM/PM) — supplementary (not a numbered deck slide)", _i95("b_i95_time_space_diagrams"),
   shows="Individual vehicle trajectories along the I-95 corridor, in four panels — northbound/southbound × AM/PM peak.",
   read="THIS is the key axes slide: the x-axis is time of day (hours) and the y-axis is distance along the corridor "
        "(chainage in km — an approximate PCA projection of the links onto the corridor axis, NOT exact mileposts). "
        "Each line is one vehicle. The SLOPE of a line is its speed — steep = fast, shallow = slow; a horizontal "
        "flat segment would be a stopped/queued vehicle. Northbound panels rise (chainage increasing), southbound "
        "descend, so each panel is truly one-directional.",
   numbers="Trajectory counts NB-AM 5,453 / NB-PM 4,855 / SB-AM 6,100 / SB-PM 4,210; corridor space-mean speed "
           "57.7–58.5 mph all day (a count-weighted aggregate — see the per-link peak-speed caveat below).",
   say="Most trajectories are straight and steep — the resident-only base is under-loaded (it omits through + "
       "commercial traffic), so the corridor runs largely free-flow at the aggregate level. Say this honestly: the "
       "corridor space-mean speed is a count-weighted DAILY aggregate that masks local peak-hour breakdown — some "
       "individual links do drop well below free-flow in the peak (per-link peak speeds fall as low as ~11 mph). The "
       "toll's full operational effect still shows up in the scenario run, not here.")

figure("I-95 corridor users — equity profile", _i95("c1_i95_user_demographics"),
   shows="The socio-demographic profile of I-95 corridor users versus the overall population, in six panels: household "
         "income, age, race/ethnicity, vehicle ownership, occupation, and income band.",
   read="Each panel compares two groups: grey = overall population, blue = I-95 users. For income and age the x-axis is "
        "the value (dollars / years) and the y-axis is the density (share of people); dashed vertical lines mark the "
        "medians. For race, vehicles, occupation and income band the x-axis is the category and the y-axis is the "
        "percent share. Read it as: where the blue bars/curve sit relative to grey = how corridor users differ.",
   numbers="Median household income $105,199 vs $96,295 overall; low-income (<$35k) 10.9% vs 14.7%; employed 81% vs 57%; "
           "race mix essentially identical (white ~52%, black ~29%).",
   say="This is the equity headline of the whole study. I-95 users are higher-income and much more likely employed, but "
       "race-neutral. So on the exposure side an uncompensated toll is NOT regressive by income incidence or by race — "
       "it lands on a higher-income commuter base. The group to watch is the ~11% low-income corridor users, for whom a "
       "flat toll is a larger budget share — the case for recycling toll revenue.")

figure("I-95 users — OD & purpose profile", _i95("c2_i95_user_od_profile"),
   shows="The origin–destination pattern (by county) and trip-purpose mix of I-95 corridor users.",
   read="Bar charts: the x-axis is the home county or the trip purpose, the y-axis is the count or share of corridor "
        "users in that category. Taller bars = more corridor users of that origin/purpose.",
   numbers="Work-dominated purpose mix; origins concentrated in the northern/western suburban counties.",
   say="Confirms the corridor is a commute corridor — mostly work trips from the suburbs — which is why an income-VOT "
       "toll (peak, commute-heavy) is the right instrument to test on it.")

figure("I-95 — flow–density fundamental diagram — supplementary (not a numbered deck slide)", _i95("d1_i95_fundamental_diagram"),
   shows="The flow–density relationship of I-95 traffic (Edie's generalised definitions) — the fundamental diagram.",
   read="x-axis = traffic density (vehicles per km); y-axis = flow (vehicles per hour). Each point is one corridor "
        "link-hour. A fundamental diagram normally rises from the origin along a free-flow branch (flow increasing with "
        "density) up to capacity, then bends back down into a congested branch (flow falling as density keeps rising).",
   numbers="Max density ≤ 233 veh/km after removing stuck-vehicle artifacts; free-flow branch correlation corr(k,q)=0.998, "
           "slope ≈ free-flow speed.",
   formula=[
     ("Edie's generalised traffic variables over a space–time region A = X · T (X = length, T = duration):",""),
     ("&nbsp;&nbsp;flow q = ( Σ<sub>i</sub> d<sub>i</sub> ) / A,&nbsp;&nbsp; density k = ( Σ<sub>i</sub> t<sub>i</sub> ) / A,"
      "&nbsp;&nbsp; space-mean speed v = q / k",
      "d<sub>i</sub> = distance each vehicle i travels inside A, t<sub>i</sub> = time it spends in A. These are the "
      "region-based generalisations that give consistent q, k, v on a heterogeneous set of links."),
   ],
   say="The free-flow branch dominates — a clean ray from the origin — the honest signature of an under-loaded "
       "resident-only base with little sustained network-wide congestion. Do not over-claim it, though: the aggregate "
       "hides local peak-hour breakdown (some link-hours sit off the free-flow branch, with peak speeds down to ~11 "
       "mph). The fuller congested branch is what the toll/through-traffic scenarios would populate.")

figure("I-95 — hourly flow & speed profiles", _i95("d2_i95_flow_speed_profiles"),
   shows="How volume and speed on I-95 vary across the 24-hour day.",
   read="x-axis = hour of day (0–23). Left y-axis = hourly volume (veh/h, scaled ×10); right y-axis = space-mean speed "
        "(mph). One curve is volume (watch for the twin commute peaks), the other is speed (watch whether it dips at the "
        "peaks).",
   numbers="Volume peaks AM ≈ 07:00 and PM ≈ 17:00; space-mean speed stays flat at ≈ 57–58 mph all day.",
   say="Volume shows the textbook morning-out / evening-back double peak, while the corridor-aggregate space-mean speed "
       "stays high at the peaks — so the base has the right temporal shape of demand with little corridor-wide "
       "congestion. Be precise: that plotted speed is a count-weighted aggregate and masks local peak-hour breakdown on "
       "individual links (peak per-link speeds fall to ~11 mph). Under pricing we would expect the peaks to flatten "
       "and, with through-traffic, speeds to dip more broadly; that contrast is the story the scenario run will tell.")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════
# CONGESTION-PRICING SCENARIO DESIGN — I-695 (deck slides 97–100)
# ══════════════════════════════════════════════════════════════════════════
section("Congestion-Pricing Scenario Design — I-695 (deck slides 97–100)",
        "The scenario the whole pipeline was built to test: a distance × time-of-day toll on the I-695 Baltimore "
        "Beltway, implemented in MATSim RoadPricing and fed back through ABIT's income-VOT mode choice. Two toll "
        "schemas bracket the response; rates are anchored to real Maryland tolled facilities so the numbers are "
        "defensible, not arbitrary.")

figure("Scenario overview — why I-695, and how it is priced (slide 97)", None,
   shows="The framing: a mainline distance/time-of-day toll on I-695 via MATSim RoadPricing. Like all freeways under "
         "the resident-only scope, the Beltway's ABSOLUTE volumes under-predict (~40%: through/E-E, commercial, and "
         "visitor traffic are excluded by design). The Beltway is chosen because it is resident-dominated, so its "
         "resident-commute STRUCTURE and AM-peak timing are well captured — and the toll result is a base-vs-toll "
         "DIFFERENCE in which the resident-only level bias largely cancels. Unlike through-heavy I-95, that difference "
         "is credible here.",
   read="No plot. Two design moves to keep in mind: (1) two toll schemas BRACKET the response (a moderate and a high "
        "level), following the MATSim-NYC two-schema method; (2) per-mile rates and peak/off/night ratios are lifted "
        "from real Maryland tolled facilities, not invented.",
   numbers="Instrument: I-695 mainline distance × time-of-day toll (RoadPricing). Why I-695 not I-95: I-695 is "
           "resident-dominated, so its resident-commute structure/spatial pattern validates (corr² up to ~0.79) even "
           "though absolute volumes under-predict ~40% under resident-only scope; the toll answer is a base→toll ΔV in "
           "which that level bias largely cancels — more reliable here than on through-traffic-heavy I-95. References: "
           "two-schema bracketing follows MATSim-NYC (He, Chow & Ozbay, arXiv 2008.04762, §5.1); rates/ratios from "
           "MD-200 ICC + I-95 Express Toll Lanes (MDTA), see toll_research/MD_toll_schemes.md.",
   say="Set up the scenario here, and be honest about the scope. We do NOT claim I-695's absolute volumes are "
       "validated — like every freeway in a resident-only model they under-predict by roughly 40% because we carry no "
       "through, commercial, or visitor traffic. What is validated is the resident-commute structure and peak timing on "
       "the Beltway, and — crucially — the policy answer is a difference between the base and the tolled run, where that "
       "level bias largely cancels. I-695 is resident-dominated, so that difference is more trustworthy here than on "
       "through-heavy I-95. Two toll levels bracket the response, MATSim-NYC style, and every rate is anchored to what "
       "Maryland already charges on the ICC and the I-95 express lanes — so nobody can call the pricing arbitrary.")

figure("Toll design — two schemas anchored to Maryland facilities (slide 98)", None,
   shows="The toll-rate table: two per-mile schemas by time-of-day, with the Maryland facilities they are anchored to "
         "and a per-trip sanity check.",
   read="Read the table as two rows (Schema A moderate, Schema B high) across three time bands (peak / off-peak / "
        "night), then the MD anchor rows that justify each level, then the per-trip bracket showing a typical I-695 "
        "trip toll sits inside the envelope Maryland already charges.",
   numbers="Schema A (moderate): $0.25 / $0.18 / $0.10 per mi (peak / off / night). Schema B (high): $0.40 / $0.30 / "
           "$0.15. MD anchors: ICC/ETL peak 0.22–0.35 $/mi; off/peak ratio ~0.73 ≈ MD 0.77; night/peak ~0.39 ≈ MD 0.32. "
           "Per-trip sanity (10-mi peak): $2.50 (A) / $4.00 (B) — brackets ICC full-length peak $3.86 and ETL segment "
           "peak $3.01, i.e. inside the range MD already charges.",
   formula=[
     ("Distance-proportional trip toll — sum the per-mile rate over the tolled links the trip uses:",""),
     ("&nbsp;&nbsp;toll<sub>trip</sub> = Σ<sub>links</sub> ( rate · length<sub>miles</sub> ) = rate · miles-on-I-695",
      "rate is the time-of-band per-mile rate; because the rate is uniform along the mainline it collapses to "
      "rate × miles driven on I-695 for that trip."),
   ],
   say="This is the rate card. Two schemas — moderate and high — each with peak, off-peak and night per-mile rates. "
       "The point of the table is that both are anchored to real Maryland tolls: the peak rates sit in the ICC / "
       "express-lane band, and the off-peak and night discounts match Maryland's own ratios. A ten-mile peak trip "
       "costs $2.50 under A and $4.00 under B — which brackets what the ICC and the I-95 express lanes charge today, "
       "so the pricing is realistic by construction.")

figure("Facility & mechanism — what is tolled and how it enters MATSim (slide 99)", None,
   shows="The concrete implementation: which links are tolled, the RoadPricing disutility, the time windows, who pays, "
         "and how the toll turns into an ABIT generalized-cost term.",
   read="Read it in four parts: the tolled facility (mainline only, ramps free), the RoadPricing disutility per link, "
        "the four time windows, and the mode incidence (full on car-driver, half on shared-ride) that becomes the ABIT "
        "cost term.",
   numbers="Facility: 604 I-695 mainline links, 92.9 directional miles, mainline-only (ramps untolled). Time windows: "
           "AM peak 06–09, PM peak 15–19, off-peak 05–06 / 09–15 / 19–23, night 23–05 (wraps midnight in the 0–36 h "
           "mobsim). Incidence: full toll on car-driver, ½ on shared-ride.",
   formula=[
     ("MATSim RoadPricing adds a disutility to each tolled link (τ = the link's toll):",""),
     ("&nbsp;&nbsp;ΔS = β<sub>money</sub> · τ",
      "τ = per-mile rate × link length; entered on every I-695 mainline link inside the active time band."),
     ("Toll → ABIT generalized cost (trip-timing-weighted daily-average per OD):",""),
     ("&nbsp;&nbsp;cost<sub>car</sub> = miles · $0.20 + toll<sub>OD</sub>,&nbsp;&nbsp; "
      "cost<sub>ride</sub> = miles · $0.20 + ½ · toll<sub>OD</sub>",
      "$0.20/mi = base auto operating cost; the toll term is the OD's average I-695 toll, weighted by when trips occur."),
   ],
   say="This is the mechanism. We toll the 604 mainline Beltway links — about 93 directional miles — and leave the "
       "ramps free. In MATSim, RoadPricing just adds a money disutility, beta-money times the link toll, on those "
       "links during the active time band. There are four bands — AM peak, PM peak, off-peak and night, with night "
       "wrapping past midnight in the extended mobsim clock. Car-drivers pay the full toll, shared-riders pay half, "
       "and that becomes the toll term in ABIT's generalized cost on top of the twenty-cents-a-mile operating cost.")

figure("Response & equity outputs — the hybrid loop and what it produces (slide 100)", None,
   shows="How the priced network is solved and what the run reports: the hybrid feedback loop, the equity mechanism, "
         "and the list of scenario outputs.",
   read="Read it as loop → mechanism → outputs. The loop nests ABIT mode choice (outer) around MATSim route/time "
        "(inner); the equity mechanism is the income-scaled VOT already in the model; the outputs are the policy "
        "deliverables broken down by income, race, age and home location.",
   numbers="Loop: OUTER = ABIT income-VOT mode choice on tolled + congested skims; INNER = MATSim ReRoute + "
           "departure-time (modes fixed); 3–5 iterations to convergence. Equity: toll / VOT with income-scaled VOT → "
           "low-income travellers shift more, high-income pay. Outputs: mode shift, toll revenue, consumer-surplus "
           "(welfare logsum) CDF by income / race / age / home, departure-time shift, network diversion. Expected "
           "result: uncompensated pricing is regressive unless revenue is recycled.",
   formula=[
     ("Equity mechanism — the fixed toll divides by an income-scaled VOT, so incidence falls harder on low income:",""),
     ("&nbsp;&nbsp;disutility ∝ toll / VOT<sub>m</sub>(I<sub>n</sub>),&nbsp;&nbsp; VOT<sub>m</sub>(I<sub>n</sub>) "
      "= VOT<sub>m</sub><super>ref</super> · (I<sub>n</sub> / I<sub>ref</sub>)<super>λ</super>",
      "λ = 0.6; low income → low VOT → the same toll is a larger disutility → larger mode shift."),
     ("Welfare change per agent via the logsum (expected maximum utility) of the mode-choice logit:",""),
     ("&nbsp;&nbsp;ΔCS<sub>n</sub> = ( 1 / β<sub>GC</sub> ) · [ ln Σ<sub>j</sub> e<sup>U<sub>n,j</sub><sup>toll</sup></sup> "
      "− ln Σ<sub>j</sub> e<sup>U<sub>n,j</sub><sup>base</sup></sup> ]",
      "reported as a CDF by income / race / age / home zone — the equity incidence the pipeline was built to produce."),
   ],
   say="This closes the deck. The priced network is solved with the same hybrid loop as the base: ABIT re-chooses mode "
       "on the tolled, congested skims on the outside, MATSim re-routes and re-times on the inside, three to five "
       "iterations to convergence. The equity result falls straight out of the income-scaled value of time — the same "
       "dollar toll is a bigger disutility for a low-income traveller, so they divert more while high earners pay and "
       "keep driving. We report mode shift, revenue, and the welfare change as a distribution by income, race, age and "
       "home location, plus departure-time shift and network diversion. The headline we expect: uncompensated pricing "
       "is regressive — which is exactly why the revenue-recycling question matters, and why this model can answer it.")

# ══════════════════════════════════════════════════════════════════════════
# SUPPLEMENTARY APPENDIX — FHWA facility-tier detail + full route table (not deck slides)
# ══════════════════════════════════════════════════════════════════════════
import aadt_appendix_spec as _aadt
def _esc(s):  # escape bare <,> so reportlab's paragraph parser doesn't choke
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
story.append(PageBreak())
section("Supplementary Appendix — FHWA Facility-Tier Detail & Full Route Table (not in the deck)",
        "Q&amp;A backup for the AADT section: the six FHWA functional-class tiers and the full per-route summary table. "
        "The per-route and design-speed-tier panels themselves are in the main flow above (deck slides 60–89). " + _esc(_aadt.CAVEAT))
for _e in _aadt.load():
    _p = str(_e["fig"])
    if not ("by_facility" in _p or "summary_table" in _p):
        continue  # per-route panels are already in the main deck-order flow
    _num = _esc(_e["cap_lines"][0])
    _scope = _esc(_e["cap_lines"][1]) if len(_e["cap_lines"]) > 1 else ""
    figure(_e["title"], _e["fig"],
       shows="Modelled versus observed 2023 AADT for this facility (against MDOT SHA counts).",
       read=("Points near the 45-degree line match the counts; read the ±facility band and median bias for daily "
             "fit rather than the strict hourly GEH. " + _scope),
       numbers=_num,
       say=_esc(_e["say"]))

# ── build ──────────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(str(OUT), pagesize=letter,
                        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                        title="VAE Presentation — Speaker Guide")
doc.build(story)
print(f"saved → {OUT}")
# keep the repo-root copy in sync
import shutil
try:
    shutil.copyfile(str(OUT), str(OUT_ROOT))
    print(f"synced → {OUT_ROOT}")
except Exception as _e:
    print(f"WARN: could not sync repo-root copy: {_e}")
