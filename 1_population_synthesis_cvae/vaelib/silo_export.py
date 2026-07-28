"""Export generated population to the SILO-input CSV schema.

Schema + enum strings verified against the SILO-validated v6 `to_silo_schema` AND the real
SILO files (SILO_MITO Models/SILO_inputs/...). SILO's readers expect STRING enums for
race/dwellingType/relationShip/jj-type and boolean strings for driversLicense.

  hh : id, dwelling, hhSize, autos, income, race
  pp : id, hhID, age, gender, race, occupation, driversLicense, workplace, income, nationality, relationShip
  dd : id, zone, type, hhID, bedrooms, quality, monthlyCost, restriction, yearBuilt
  jj : id, zone, personId, type
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config

# verified vs vae_silo_v6/generate.py (SILO-ingested) + real SILO files
DWELLING_TYPE_TO_SILO = {1: "SFD", 2: "SFA", 3: "MF234", 4: "MF5plus", 5: "MH"}
RACE_TO_SILO = {1: "white", 2: "black", 3: "hispanic", 4: "other", 5: "other"}  # Asian→other (v6 lock)
OCCUPATION_TO_SILO = {1: 1, 2: 3, 3: 4, 4: 2, 5: 0, 6: 2}  # →SILO int: EMPLOYED1 STUDENT3 RETIREE4 UNEMP2 TODDLER0
LICENSE_TO_SILO = {0: "false", 1: "true"}
JOB_TYPES = ["RET", "OFF", "IND", "OTH"]


def _relationship_str(pp_df: pd.DataFrame) -> pd.Series:
    """internal relationship → SILO {SINGLE, MARRIED, CHILD} (v6 logic). Vectorized."""
    rel = pp_df["relationship"].to_numpy()
    spouse_hh = pd.unique(pp_df.loc[rel == 1, "hh_id"])           # HHs with a spouse
    has_spouse = pp_df["hh_id"].isin(spouse_hh).to_numpy()
    out = np.full(len(pp_df), "SINGLE", dtype=object)
    out[(rel == 0) & has_spouse] = "MARRIED"
    out[rel == 1] = "MARRIED"
    out[rel == 2] = "CHILD"
    return pd.Series(out, index=pp_df.index)


def _hh_race_str(gen_pp: pd.DataFrame) -> pd.Series:
    """majority person race per household → SILO race string. Vectorized (np.add.at)."""
    hids, hpos = np.unique(gen_pp["hh_id"].to_numpy(), return_inverse=True)
    race = np.clip(gen_pp["race"].to_numpy(int) - 1, 0, 4)
    counts = np.zeros((len(hids), 5))
    np.add.at(counts, (hpos, race), 1)
    maj = counts.argmax(1) + 1                                    # internal race 1..5
    s = pd.Series(maj, index=hids).map(RACE_TO_SILO).fillna("other")
    return s


def _assign_job_types(jj_df: pd.DataFrame, rng) -> np.ndarray:
    """Type each job RET/OFF/IND/OTH by its zone's 2016 employment mix (forecast)."""
    f = pd.read_csv(config.FORECAST_CSV)
    zc = "SMZ" if "SMZ" in f.columns else f.columns[0]
    cols = {t: f"{t}16" for t in JOB_TYPES}
    if not all(c in f.columns for c in cols.values()):
        return np.full(len(jj_df), "OTH")
    mix = f.set_index(zc)[[cols[t] for t in JOB_TYPES]].clip(lower=0)
    shares = mix.div(mix.sum(1).replace(0, np.nan), axis=0).fillna(0.25)
    reg = (mix.sum() / mix.sum().sum()).to_numpy()
    out = np.empty(len(jj_df), dtype=object)
    for z, grp in jj_df.groupby("zone", sort=False):
        p = shares.loc[z].to_numpy() if z in shares.index else reg
        if p.sum() <= 0:
            p = reg
        out[grp.index.to_numpy()] = rng.choice(JOB_TYPES, size=len(grp), p=p / p.sum())
    return out


def to_silo_schema(gen_hh, gen_pp, out_dir, base_year=2016, jj_df=None,
                   workplace_by_pp=None, seed=0):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    y = base_year; rng = np.random.default_rng(seed)
    gen_pp = gen_pp.reset_index(drop=True)

    # households: id, dwelling, hhSize, autos, income, race
    hh_race = _hh_race_str(gen_pp)
    hh = pd.DataFrame({
        "id": gen_hh["hh_id"].astype(int),
        "dwelling": gen_hh["hh_id"].astype(int),
        "hhSize": gen_hh["hhSize"].astype(int),
        "autos": gen_hh["autos"].astype(int),
        "income": gen_hh["income_hh"].clip(lower=0).astype(int),
        "race": gen_hh["hh_id"].map(hh_race).fillna("other").astype(str),
    })
    hh.to_csv(out / f"hh_{y}.csv", index=False)

    # dwellings: id, zone, type, hhID, bedrooms, quality, monthlyCost, restriction, yearBuilt
    dd = pd.DataFrame({
        "id": gen_hh["hh_id"].astype(int),
        "zone": gen_hh["zone_id"].astype(int),
        "type": gen_hh["dwellingType"].astype(int).map(DWELLING_TYPE_TO_SILO).fillna("SFD"),
        "hhID": gen_hh["hh_id"].astype(int),
        "bedrooms": gen_hh.get("bedrooms", 2).astype(int),
        "quality": 3,
        "monthlyCost": gen_hh.get("monthlyCost", 0).astype(int),
        "restriction": 0,
        "yearBuilt": gen_hh.get("yearBuilt", 1985).astype(int),
    })
    dd.to_csv(out / f"dd_{y}.csv", index=False)

    # persons
    wp = (gen_pp["pp_id"].map(workplace_by_pp).fillna(-1).astype(int)
          if workplace_by_pp is not None else pd.Series(-1, index=gen_pp.index))
    pp = pd.DataFrame({
        "id": gen_pp["pp_id"].astype(int),
        "hhID": gen_pp["hh_id"].astype(int),
        "age": gen_pp["age"].astype(int),
        "gender": gen_pp["gender"].astype(int),
        "race": gen_pp["race"].astype(int).map(RACE_TO_SILO).fillna("other"),
        "occupation": gen_pp["occupation"].astype(int).map(OCCUPATION_TO_SILO).fillna(2).astype(int),
        "driversLicense": gen_pp["driversLicense"].astype(int).map(LICENSE_TO_SILO),
        "workplace": wp.values,
        "income": gen_pp["income"].clip(lower=0).astype(int),
        "nationality": (gen_pp["nationality"].astype(int) if "nationality" in gen_pp.columns else 1),
        "relationShip": _relationship_str(gen_pp).values,
    })
    pp.to_csv(out / f"pp_{y}.csv", index=False)

    # jobs: id, zone, personId, type
    if jj_df is None or len(jj_df) == 0:
        jj_df = pd.DataFrame(columns=["id", "zone", "personId", "type"])
    else:
        jj_df = jj_df.rename(columns={"workerID": "personId"}).reset_index(drop=True)
        jj_df = pd.DataFrame({"id": jj_df["id"].astype(int), "zone": jj_df["zone"].astype(int),
                              "personId": jj_df.get("personId", jj_df.get("workerID", -1)).astype(int),
                              "type": _assign_job_types(jj_df, rng)})
    jj_df.to_csv(out / f"jj_{y}.csv", index=False)

    return {"hh": out / f"hh_{y}.csv", "pp": out / f"pp_{y}.csv",
            "dd": out / f"dd_{y}.csv", "jj": out / f"jj_{y}.csv"}
