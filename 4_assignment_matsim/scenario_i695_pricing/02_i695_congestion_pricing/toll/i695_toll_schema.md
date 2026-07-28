# I-695 Baltimore Beltway — time-of-day congestion-pricing schema

Analog of MATSim-NYC Table 6 (paper `2008.04762v2.pdf`, Sec. 5.1), grounded in real Maryland toll
precedent (see `../../toll_research/MD_toll_schemes.md`). Two schemas — a **Moderate** and a **High**
price — are defined so we can bracket the response the way NYC bracketed Schema 1 ($9.18) vs Schema 2
($14). Behavioral response is entirely via MATSim's inner loop (ReRoute + TimeAllocationMutator +
SubtourModeChoice); **no outer loop**.

## Facility tolled
- **I-695 mainline, full Beltway loop, both directions** = **604 network links, 92.92 directional miles**
  (real loop ≈ 51 mi one-way ≈ 102 mi both ways; the ~9-mi shortfall is the collapsed Francis Scott
  Key Bridge harbor crossing, absent from the OSM snapshot). Link set in
  `../../toll_research/i695_link_ids.txt` (matched on `osm:way:name="Baltimore Beltway"`, all
  `highway=motorway`, freespeed ~55 mph, CRS EPSG:26985).
- Only the **mainline** is tolled — interchange ramps and the roads I-695 connects to are untolled, so
  the toll bites on *through / around-the-Beltway* travel, exactly the movement congestion pricing
  targets.

## The two schemas (per-mile, distance-proportional)

Unlike NYC's flat cordon charge, I-695 is a long facility, so — following MDTA's own ETL/ICC practice —
the toll is levied **per mile**. A trip pays `rate × miles driven on I-695`. Rates and the peak/off-peak/
overnight ratio structure are lifted directly from the I-95 ETL and MD-200 ICC (both ~0.77 off-peak and
~0.32 overnight relative to peak).

### Table 1. Simulated I-695 charging schemas (2-axle car, per mile)

| Period (window) | **Schema A — Moderate** | **Schema B — High** | MD anchor |
|---|---|---|---|
| **Peak** (06:00–09:00, 15:00–19:00) | **$0.25/mi** | **$0.40/mi** | ICC/ETL peak 0.22–0.35 $/mi |
| **Off-peak** (05:00–06:00, 09:00–15:00, 19:00–23:00) | **$0.18/mi** | **$0.30/mi** | ICC off-peak 0.17–0.30; ratio 0.72–0.75 ≈ MD 0.77 |
| **Night** (23:00–05:00) | **$0.10/mi** | **$0.15/mi** | ICC/ETL overnight; ratio 0.38–0.40 ≈ MD 0.32 |

### Table 2. Resulting per-trip charge (sanity check)

| Trip on I-695 | Schema A peak / off / night | Schema B peak / off / night |
|---|---|---|
| 10 mi (typical Beltway segment) | $2.50 / $1.80 / $1.00 | $4.00 / $3.00 / $1.50 |
| Full loop one-way (~51 mi, ~46 mi modeled) | ~$11.6 | ~$18.6 |

The 10-mi peak charge ($2.50 / $4.00) brackets the ICC full-length peak toll ($3.86) and the ETL segment
peak ($3.01) — i.e. both schemas are **within the envelope MD already charges**, with A at the ICC's
effective rate and B at the top of the approved ETL range. The full-loop figures are large but
irrelevant in practice (essentially nobody drives the entire Beltway); the per-mile design makes the
charge proportional to actual Beltway use.

## Time windows (implementation, seconds from 00:00)
MATSim runs a single representative weekday, mobsim 0–36 h. Night wraps midnight, so the late block runs
23:00→30:00 to toll post-midnight legs of the modeled day.

| Window | start | end |
|---|---|---|
| Night | 00:00:00 | 05:00:00 |
| Off-peak (early) | 05:00:00 | 06:00:00 |
| **Peak (AM)** | 06:00:00 | 09:00:00 |
| Off-peak (mid) | 09:00:00 | 15:00:00 |
| **Peak (PM)** | 15:00:00 | 19:00:00 |
| Off-peak (eve) | 19:00:00 | 23:00:00 |
| Night (late) | 23:00:00 | 30:00:00 |

Both directions get the **same** peak in both AM and PM: a beltway is congested clockwise and
counter-clockwise in both peaks (unlike a radial), so a directional split is not warranted.

## MATSim implementation

- **Extension:** `org.matsim.contrib.roadpricing` (the same "Road Pricing" extension MATSim-NYC used,
  paper Sec. 5.2). The toll is scored as a monetary disutility on the agent's day and thus feeds
  route- and time-choice in the inner loop.
- **File:** `roadpricing_i695.xml` in this folder — `type="link"`, one `<link>` per tolled I-695 link,
  with seven per-link `<cost>` rows (the windows above). Each link's amount = `rate(window) ×
  link_length_miles`, so summing over a trip's links reproduces the per-mile toll. **Schema A** is the
  committed draft; regenerate Schema B with `python ../../toll_research/build_roadpricing_i695.py B
  roadpricing_i695_high.xml`.
- **DTD note:** the roadpricing DTD bundled in the current runner jar is `roadpricing_v1.dtd`, whose
  comment lists only `distance | area | cordon`. The modern `org.matsim.contrib.roadpricing`
  `RoadPricingScheme` also supports **`link`** (per-link, per-time amount charged once per traversal),
  which is what we use. If a stricter v1 validator ever rejects `type="link"`, the exact equivalent is
  `type="distance"` with a single global `<cost>` per window at `amount = rate/1609.344` ($/meter) —
  identical charge, fewer rows. `build_roadpricing_i695.py` can be switched to emit that.
- **Charged once per direction of travel** (per link traversal), not two-way-on-a-cordon like NYC —
  appropriate for a per-mile facility toll.

## What we measure (per the study aims)
Route diversion off I-695, departure-time shift out of the peak windows, and mode shift — resolved by
population segment (income, race, age, home location) using the ABIT resident demand. Consumer-surplus /
disutility of the toll uses `marginalUtilityOfMoney` from the scorer (see `../MODE_SCORER_MAPPING.md`).
