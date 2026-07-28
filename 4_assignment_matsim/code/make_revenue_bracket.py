#!/usr/bin/env python3
"""Revenue/usage bracket for the I-695 pricing scenario: income-based VTTS heterogeneity (our model)
vs usage-frequency-based VTTS heterogeneity (Lin, Spissu & Cirillo 2025, RTE 114:101671).

Method: a traveler facing toll tau with time saving dt (vs best free alternative) pays iff
VTTS > tau/dt. Given the scenario's observed (tau, dt) exposure distribution, usage and revenue are
re-evaluated under each VTTS distribution. The gap brackets the structural uncertainty in HOW
heterogeneity is organized (income- vs familiarity/urgency-structured), holding exposure fixed.

Inputs:
  crossings.csv   one row per potential tolled crossing: tau ($), dt_min (minutes saved vs best
                  free alternative), n (expanded count). Produced by the scenario post-processing
                  (toll-leg events x base-leg alternative times).
  population      matsim population xml.gz (for the income-based VTTS distribution)
Usage: make_revenue_bracket.py <crossings.csv> <population.xml.gz> <out_dir>
"""
import sys, os, gzip
import numpy as np, pandas as pd
import xml.etree.ElementTree as ET
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

CROSS, POP, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.family":"serif","font.serif":["Times New Roman","Times","DejaVu Serif"],
    "font.size":9,"axes.spines.top":False,"axes.spines.right":False,"axes.linewidth":0.8})

# ---- Distribution A: OUR income-based VTTS (Cirillo 2017 gradient + 2024 anchor, 2023$) ----
#   VTTS_p = 31.8 / clamp(lambda(I_p)/lambda(I_med), 0.4, 2.5)
B1, TWO_B2 = 0.525, -0.002
TPY = 2.88 * 260.0
DEFL_2016_2011 = 1 / 1.067
VOT_MED = 31.8
def income_vtts(incomes):
    inc = np.asarray(incomes, float)
    lam = B1 + TWO_B2 * (inc * DEFL_2016_2011 / TPY)
    med = np.median(inc)
    lam_med = B1 + TWO_B2 * (med * DEFL_2016_2011 / TPY)
    fac = np.clip(lam / lam_med, 0.4, 2.5)
    return VOT_MED / fac

print("reading population incomes...")
incs = []
for _, el in ET.iterparse(gzip.open(POP, "rb"), events=("end",)):
    if el.tag != "person": continue
    a = {at.get("name"): at.text for at in el.findall("attributes/attribute")}
    try: incs.append(float(a.get("hhIncome", "nan")))
    except: pass
    el.clear()
vtts_income = income_vtts([i for i in incs if np.isfinite(i)])

# ---- Distribution B: Lin, Spissu & Cirillo (2025) usage-frequency mixture ----
# Table 1 population shares (by EL trip-frequency category) x Table 4 GOL VTTS ($/h, pre-pandemic $
# -> expressed in 2023$ with the same CPI factor 1.18 used for the anchor, for unit consistency).
CPI = 1.18
FREQ_SHARES = np.array([0.5115, 0.3845, 0.0513, 0.0197, 0.0115, 0.0078, 0.0046, 0.0091])
FREQ_VTTS   = np.array([56.43, 9.49, 4.51, 2.97, 2.19, 1.67, 1.40, 1.40]) * CPI

def usage_revenue(cr, dist_draws=None, mix=None):
    """cr: DataFrame(tau, dt_min, n). Returns (users, revenue) under a VTTS distribution given
    either as draws (empirical array, $/h) or as a discrete mixture (shares, values)."""
    crit = 60.0 * cr.tau / cr.dt_min.clip(lower=0.1)          # critical VTTS $/h
    if dist_draws is not None:
        d = np.sort(dist_draws)
        p_pay = 1.0 - np.searchsorted(d, crit, side="right") / len(d)
    else:
        shares, vals = mix
        p_pay = np.array([shares[vals > c].sum() for c in crit])
    users = (cr.n * p_pay).sum()
    revenue = (cr.n * p_pay * cr.tau).sum()
    return users, revenue

cr = pd.read_csv(CROSS)
uA, rA = usage_revenue(cr, dist_draws=vtts_income)
uB, rB = usage_revenue(cr, mix=(FREQ_SHARES, FREQ_VTTS))
res = pd.DataFrame([
    dict(distribution="Income-based (Cirillo 2017 gradient, 2024 anchor)", users=int(uA), revenue=round(rA)),
    dict(distribution="Frequency-based (Lin, Spissu & Cirillo 2025)",     users=int(uB), revenue=round(rB)),
])
res["revenue_ratio_vs_income"] = (res.revenue / rA).round(3)
res.to_csv(f"{OUT}/revenue_bracket.csv", index=False)
print(res.to_string(index=False))

# ---- figure: the two demand curves over the scenario's critical-VTTS range ----
xs = np.linspace(0.5, 80, 300)
d = np.sort(vtts_income)
pA = 1.0 - np.searchsorted(d, xs, side="right") / len(d)
pB = [FREQ_SHARES[FREQ_VTTS > x].sum() for x in xs]
fig, ax = plt.subplots(figsize=(4.8, 3.4))
ax.plot(xs, 100*np.asarray(pA), lw=1.6, color="#0072B2", label="Income-based (this model)")
ax.plot(xs, 100*np.asarray(pB), lw=1.6, color="#D55E00", ls="--", label="Frequency-based (Lin et al. 2025)")
ax.set_xlabel("Critical VTTS = toll per hour saved ($/h, 2023$)")
ax.set_ylabel("Share willing to pay (%)")
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(f"{OUT}/fig_vtts_demand_curves.png", dpi=600, bbox_inches="tight")
fig.savefig(f"{OUT}/fig_vtts_demand_curves.pdf", bbox_inches="tight")
print("saved fig_vtts_demand_curves + revenue_bracket.csv")
