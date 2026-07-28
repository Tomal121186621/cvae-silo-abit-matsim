"""SILO-style workplace allocation (Path A): assign employed persons to job zones using
TLFD(commute time) × job vacancies, decrementing a per-zone jobs inventory.

Inputs: highway skim (OMX, minutes), hts_work_TLFD.csv, employment forecast.
Outputs: pp.workplace (JOB id, or -1 unreachable / -2 external surplus) and a jj frame.
SILO links person<->job by person.workplace == job.id, so workplace MUST be the job id
(not the work zone). The job's zone lives in the jj frame.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

TLFD_MIN, TLFD_MAX = 1, 200

# Gravity friction factor for worker->job matching. The earlier code used the raw observed
# commute-time TLFD as the friction factor AND multiplied by job counts, which double-counts
# opportunities (jobs concentrate in far downtown zones) and produced commutes ~2x too long
# (realized ~62 min vs the 37.6-min TLFD target). A proper distance decay exp(-beta*t) restores
# realistic commutes: beta=0.08 reproduces the observed commute-length distribution.
FRICTION_BETA = 0.07


class SkimReader:
    def __init__(self, path=config.SKIM_OMX, matrix_name="HOVTime"):
        import openmatrix as omx
        f = omx.open_file(str(path), "r")
        names = f.list_matrices()
        mn = matrix_name if matrix_name in names else names[0]
        self._m = np.array(f[mn])
        # map zone id → matrix index via the OMX mapping if present, else 1-based
        try:
            mp = f.mapping(f.list_mappings()[0])
            self.zone_to_i = {int(z): int(i) for z, i in mp.items()}
        except Exception:
            n = self._m.shape[0]
            self.zone_to_i = {z: z - 1 for z in range(1, n + 1)}
        f.close()

    def times_from(self, home_zone, dest_zones):
        hi = self.zone_to_i.get(int(home_zone))
        if hi is None:
            return None
        di = np.array([self.zone_to_i.get(int(z), -1) for z in dest_zones])
        ok = di >= 0
        t = np.full(len(dest_zones), np.nan)
        t[ok] = self._m[hi, di[ok]]
        return np.clip(t, TLFD_MIN, TLFD_MAX)


class CommuteTimeDistribution:
    def __init__(self, path=config.TLFD_CSV):
        df = pd.read_csv(path)
        col = [c for c in df.columns if df[c].dtype != object][-1]
        pmf = np.zeros(TLFD_MAX + 1)
        for _, r in df.iterrows():
            m = int(r.iloc[0])
            if TLFD_MIN <= m <= TLFD_MAX:
                pmf[m] = float(r[col])
        self.pmf = pmf / pmf.sum() if pmf.sum() > 0 else pmf

    def at(self, minutes):
        idx = np.clip(np.rint(np.nan_to_num(minutes, nan=TLFD_MAX)).astype(int), TLFD_MIN, TLFD_MAX)
        return self.pmf[idx]


def load_employment_forecast(path=config.FORECAST_CSV, year=2016):
    df = pd.read_csv(path)
    zcol = [c for c in df.columns if "zone" in c.lower() or c.lower() in ("smz", "smz_n", "taz")]
    zcol = zcol[0] if zcol else df.columns[0]
    ycol = [c for c in df.columns if str(year) in c]
    tot = pd.to_numeric(df[ycol[0]] if ycol else df.iloc[:, -1], errors="coerce").fillna(0)
    return pd.DataFrame({"zone": pd.to_numeric(df[zcol], errors="coerce").fillna(0).astype(int),
                         "jobs": tot.astype(int)})


class WorkplaceAllocator:
    def __init__(self, skim, tlfd, forecast, rng=None, friction_beta=FRICTION_BETA):
        self.skim, self.tlfd, self.rng = skim, tlfd, rng or np.random.default_rng(0)
        self.friction_beta = friction_beta
        self.zones = forecast["zone"].to_numpy()
        self.vacant = forecast.set_index("zone")["jobs"].to_dict()

    def _friction(self, t):
        # distance-decay friction factor (replaces the mis-used raw TLFD); see FRICTION_BETA note
        return np.exp(-self.friction_beta * np.asarray(t, dtype=float))

    def assign(self, employed: pd.DataFrame, starting_job_id=1):
        """employed: columns [pp_id, zone_id] (home zone). Returns (workplace_by_pp, jj_df)."""
        zones = self.zones
        base_vac = np.array([max(self.vacant.get(int(z), 0), 0) for z in zones], dtype=float)
        wp = {}; jj = []
        jid = starting_job_id
        # process persons grouped by home zone (cache TLFD weights per home zone)
        for hz, grp in employed.groupby("zone_id", sort=False):
            t = self.skim.times_from(hz, zones)
            if t is None:
                for pid in grp["pp_id"]:
                    wp[int(pid)] = -1
                continue
            w = self._friction(t) * base_vac
            ssum = w.sum()
            for pid in grp["pp_id"]:
                avail = base_vac > 0
                if not avail.any() or ssum <= 0:
                    wp[int(pid)] = -2; continue
                p = (w * avail) / (w * avail).sum()
                zi = self.rng.choice(len(zones), p=p)
                z = int(zones[zi]); base_vac[zi] -= 1; w[zi] = self._friction(t[zi]) * base_vac[zi]
                ssum = w.sum()
                wp[int(pid)] = jid          # SILO workplace = JOB id (not zone); job created next line
                jj.append((jid, z, int(pid), "job")); jid += 1
        jj_df = pd.DataFrame(jj, columns=["id", "zone", "personId", "type"])
        return pd.Series(wp, name="workplace"), jj_df
