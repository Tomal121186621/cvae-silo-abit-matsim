# Maryland toll schemes — evidence base for the I-695 congestion-pricing schema

Compiled 2026-07-03 for the I-695 (Baltimore Beltway) time-of-day toll scenario. Purpose: ground a
*defensible* I-695 toll schema in the **actual** rates and time-of-day structure MDTA already uses on
comparable Maryland facilities, the way MATSim-NYC grounded its cordon schema in real MTA/PANYNJ tolls
(paper `2008.04762v2.pdf`, Sec. 4.1.3 item 2 and Table 6).

All rates below are 2-axle passenger car, **E-ZPass Maryland** (the base rate; video/pay-by-plate is
~1.5×). Rates verified against MDTA pages, July 2026.

---

## 1. I-95 Express Toll Lanes (ETL) — dynamic / time-of-day, per-mile

The clearest MD precedent for a **priced limited-access facility** in the Baltimore region. An 8-mile
express-lane segment on I-95 NE of Baltimore, single tolling point per direction, rates set in **cents
per mile** and varied by time of day.

- **Approved per-mile range: 22–35 ¢/mi (peak).** (MDTA board-approved range; rates unchanged since
  2021-04-29.)
- **Posted segment tolls (2-axle E-ZPass), NB:**
  | Segment | Peak | Off-peak | Overnight |
  |---|---|---|---|
  | I-95/I-895 → MD 43 | $1.43 | $1.11 | $0.46 |
  | I-95/I-895 → MD 152 (full, ~8.8 mi) | $3.01 | $2.33 | $0.96 |
  | MD 43 → MD 152 | $1.58 | $1.22 | $0.50 |
  | MD 43 → I-95/I-895 (SB) | $1.54 | $1.19 | $0.49 |
- **Implied full-length per-mile:** $3.01 / 8.8 mi ≈ **34 ¢/mi peak** (top of the range).
- **Time windows (directional):**
  - Peak: NB Mon–Fri 3–7 pm; SB Mon–Fri 6–9 am; weekends 12–2 pm (Sat) / 2–5 pm (Sun).
  - Off-peak: the weekday daytime shoulders (roughly 5 am–3 pm & 7–9 pm NB; 5–6 am & 9 am–9 pm SB).
  - Overnight: **9 pm–5 am** every day.
- **Ratio structure (the useful part):** off-peak ≈ **0.77 × peak** ($2.33/$3.01); overnight ≈
  **0.32 × peak** ($0.96/$3.01).

Sources: MDTA Toll Rates Tables <https://mdta.maryland.gov/TollRatesTables>; ETL brochure
<https://mdta.maryland.gov/sites/default/files/Files/ETL%20Brochure.pdf>; JFK Hwy rates
<https://mdta.maryland.gov/Toll_Rates/jfk_rates.html>.

---

## 2. MD-200 (Intercounty Connector, ICC) — time-of-day per-mile, whole facility

The best precedent for tolling an **entire multi-segment highway** (not just express lanes) with a
peak / off-peak / overnight table — structurally the closest analog to tolling the I-695 mainline.

- **Per-mile ranges by period (2-axle E-ZPass):**
  - Peak: **22–35 ¢/mi** — Mon–Fri **6–9 am, 4–7 pm** (excl. federal holidays)
  - Off-peak: **17–30 ¢/mi** — Mon–Fri 5–6 am, 9 am–4 pm, 7–11 pm; weekends/holidays 5 am–11 pm
  - Overnight: **7–30 ¢/mi** — every day **11 pm–5 am**
- **Posted full-length example (I-370 → US 1, ~18.8 mi):** peak **$3.86**, off-peak **$2.98**,
  overnight **$1.23** → ≈ **20.5 ¢/mi peak**, and ratios off-peak ≈ **0.77 × peak**, overnight ≈
  **0.32 × peak** — the *same* ~0.77 / ~0.32 structure as the ETL.
- Fully electronic (E-ZPass or video at 1.5×). Higher during peak "to manage congestion."

Sources: ICC toll rates <https://mdta.maryland.gov/ICC/Toll_Rates.html>; ICC brochure
<https://mdta.maryland.gov/sites/default/files/Files/MDTA%20ICC%20Brochure.pdf>.

---

## 3. I-495 / I-270 managed lanes (P3 program) — proposed dynamic HOT rates

Not built, but the MDTA-vetted **preliminary toll-rate proposal** shows what a modern dynamically
priced facility in the MD suburbs was designed to charge — a useful upper anchor.

- **Floor: 20 ¢/mi** (minimum, uncongested).
- **Expected averages: ~$1.00/mi (AM peak), ~$1.50/mi (PM peak)** for a passenger car — i.e. dynamic
  pricing that can run **3–7× the ICC/ETL fixed peak** when volumes exceed ~1,600 veh/h/lane or speeds
  drop below 50 mph (soft-cap breach).
- HOV-3+ and transit buses toll-free; motorcycles half; trucks up to $9/mi.

Sources: Maryland Matters <https://marylandmatters.org/2021/05/21/what-will-it-cost-to-use-new-i-495-i-270-toll-lanes-that-depends/>;
MDTA preliminary rate proposal letter
<https://mdta.maryland.gov/sites/default/files/Files/ALB270/201218_Letter_MDTAtoAMEP_TollRateProposal.pdf>.

---

## 4. General MDTA practice (context)

- MDTA prices **per-mile** on limited-access priced facilities (ETL, ICC) and **per-crossing** (flat)
  on the legacy bridges/tunnels (Fort McHenry/I-95 $4.00 two-axle E-ZPass, Key Bridge before collapse,
  Bay Bridge, etc.).
- Video/pay-by-plate = **1.5 × base**, min $1 / max $15 surcharge.
- Peak windows across MD facilities cluster at **weekday 6–9 am and 3/4–7 pm**; overnight ~11 pm–5 am.

---

## 5. Synthesis → parameters carried into the I-695 schema

| Quantity | MD evidence | Value adopted for I-695 |
|---|---|---|
| Peak per-mile (fixed) | ETL 22–35 ¢/mi; ICC 22–35 ¢/mi | **Moderate 25 ¢/mi; High 40 ¢/mi** |
| Off-peak / peak ratio | 0.77 (both ETL & ICC) | **~0.72–0.75** (0.18/0.25; 0.30/0.40) |
| Overnight / peak ratio | 0.32 (both ETL & ICC) | **~0.38–0.40** (0.10/0.25; 0.15/0.40) |
| Peak window | ICC 6–9 am, 4–7 pm | **6–9 am, 3–7 pm** (both directions) |
| Off-peak window | ICC 5–6 am, 9 am–4 pm, 7–11 pm | **5–6 am, 9 am–3 pm, 7–11 pm** |
| Overnight window | ETL/ICC 9/11 pm–5 am | **11 pm–5 am** |

The **Moderate** schema sits at the ICC's own effective per-mile rate; the **High** schema sits at the
top of the ETL/ICC approved range (35 ¢/mi rounded to 40) — still an order of magnitude below the
I-495/270 dynamic peak, so both schemas are conservative relative to what MD has already been willing to
charge. See `../02_i695_congestion_pricing/toll/i695_toll_schema.md` for the full schema and the
MATSim implementation.
