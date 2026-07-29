# I-695 pricing sweep — run manifest (2 networks x 3 pricing levels)

All runs: identical demand (frozen base plans = 01_base/output_calib_fs/pass7/output_plans.xml.gz),
identical config (-Dmodechoice=true -Dinnovoff=1.0 -Dsmc.weight=0.04, ASCs pt 0.75/ride -0.60/
walk 0.10/bike -2.10, 15 iters, flow 0.10/storage 0.40, Xmx10g). Only the toll file and the
bridge links differ. Sample = 10% (x10 to expand).

| run | network | pricing | dir | status |
|---|---|---|---|---|
| bridge_base    | v14kb (bridge in)     | existing MDTA only          | ../01_base_no_pricing/output_calib_fs/pass8 (linkstats it.10) + pass7 plans | DONE (frozen base) |
| bridge_tollA   | v14kb                 | Schema A 0.25/0.18/0.10 $/mi + existing | runs/bridge_tollA | RUNNING |
| bridge_tollB   | v14kb                 | Schema B 0.40/0.30/0.15 $/mi + existing | runs/bridge_tollB | pending |
| nobridge_base  | v14kb minus keybridge | existing minus KB           | runs/nobridge_base | pending |
| nobridge_tollA | v14kb minus keybridge | Schema A (604 links)        | runs/nobridge_tollA | pending |
| nobridge_tollB | optional              |                             | | optional |

Toll files in ../toll/ ; no-bridge network in ../networks/ when built.
