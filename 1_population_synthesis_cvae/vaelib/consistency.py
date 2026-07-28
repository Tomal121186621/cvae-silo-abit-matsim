"""Structural-zero (impossible-combination) enforcement + verification.

Because exact age is drawn within the 5-year bin AFTER sampling, age-threshold constraints
are enforced deterministically on the exact age at generation (hard logical rules, not
statistical patches). `count_structural_zeros` then verifies 0 remain (validation category 8).

Internal occupation codes: 1=employed, 2=student, 3=retiree, 4=unemployed, 5=toddler, 6=other.
Relationship: 0=householder, 1=spouse, 2=child, ... .
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def apply_constraints(pp: pd.DataFrame) -> pd.DataFrame:
    """Enforce hard age-based logical rules on exact age. Returns a corrected copy."""
    pp = pp.copy()
    age = pd.to_numeric(pp["age"], errors="coerce").fillna(0).to_numpy()
    occ = pp["occupation"].to_numpy().copy()
    lic = pp["driversLicense"].to_numpy().copy()
    rel = pp["relationship"].to_numpy().copy()

    under6, child_age, adult = age < 6, (age >= 6) & (age < 16), age >= 16
    occ[under6] = 5                                   # toddlers
    occ[(age >= 6) & (occ == 5)] = np.where(age[(age >= 6) & (occ == 5)] < 16, 2, 6)  # no toddler ≥6
    occ[child_age & np.isin(occ, [1, 3])] = 2         # no employed/retiree 6–15 → student
    occ[(age < 62) & (occ == 3)] = 6                  # no retiree <62 → other
    lic[age < 16] = 0                                 # no license <16
    rel[(rel == 1) & (age < 16)] = 2                  # no spouse <16 → child

    pp["occupation"] = occ; pp["driversLicense"] = lic; pp["relationship"] = rel
    # income coherence with occupation: toddlers earn nothing
    if "income" in pp.columns:
        inc = pd.to_numeric(pp["income"], errors="coerce").fillna(0).to_numpy()
        inc[occ == 5] = 0
        pp["income"] = inc
    return pp


def enforce_one_householder(pp: pd.DataFrame) -> pd.DataFrame:
    """Exactly one householder per household: the first person (min sporder) is the
    householder (relationship 0); any other spurious householder → 7 (other/non-relative)."""
    pp = pp.sort_values(["hh_id", "sporder"], kind="stable").reset_index(drop=True)
    rel = pp["relationship"].to_numpy().copy()
    is_first = ~pp["hh_id"].duplicated().to_numpy()   # first per hh in sporder order
    rel[is_first] = 0
    rel[(~is_first) & (rel == 0)] = 7
    pp = pp.copy(); pp["relationship"] = rel
    return pp


def count_structural_zeros(pp: pd.DataFrame, hh: pd.DataFrame | None = None,
                           jj: pd.DataFrame | None = None) -> dict:
    """Count impossible combinations. All should be 0 after apply_constraints."""
    age = pd.to_numeric(pp["age"], errors="coerce").fillna(0).to_numpy()
    occ = pp["occupation"].to_numpy(); lic = pp["driversLicense"].to_numpy()
    rel = pp["relationship"].to_numpy(); ab = pp["age_bin"].to_numpy()
    bin_lo = ab * 5; bin_hi = np.where(ab >= 17, 99, ab * 5 + 4)
    out = {
        "license_under16": int(((lic == 1) & (age < 16)).sum()),
        "employed_under16": int(((occ == 1) & (age < 16)).sum()),
        "retiree_under62": int(((occ == 3) & (age < 62)).sum()),
        "toddler_over5": int(((occ == 5) & (age >= 6)).sum()),
        "nontoddler_under6": int(((occ != 5) & (age < 6)).sum()),
        "spouse_under16": int(((rel == 1) & (age < 16)).sum()),
        "age_outside_bin": int(((age < bin_lo) | (age > bin_hi)).sum()),
    }
    if hh is not None:
        n_head = pp.groupby("hh_id")["relationship"].apply(lambda r: int((r == 0).sum()))
        out["hh_not_one_householder"] = int((n_head != 1).sum())
    if jj is not None and "personId" in jj.columns:
        emp = set(pp.loc[pp["occupation"] == 1, "pp_id"])
        held = jj.loc[jj["personId"] > 0, "personId"]
        out["job_held_by_nonemployed"] = int((~held.isin(emp)).sum())
    out["total"] = int(sum(v for k, v in out.items() if k != "total"))
    return out
