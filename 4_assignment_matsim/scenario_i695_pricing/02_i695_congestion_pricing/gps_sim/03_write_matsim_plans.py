#!/usr/bin/env python3
"""Step 3: write a minimal MATSim population (plans.xml.gz) + config for the GPS-derived
I-95 trips. Each person = one GPS trip: home act at O (EPSG:26985), car leg, work act at D,
departure = local (utc_timestamp_1 + utc_offset_1) seconds-of-day. This is the GPS-derived
MATSim input the shortest-path router consumed; it can also be fed to a full MATSim mobsim."""
import gzip, os
import numpy as np, pandas as pd

BASE = "/Users/tomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Updated MATSim"
CACHE = f"{BASE}/network_validation_2023/FINAL_FIGURES/i95_gps_vs_model/cache"
GPS_IN = f"{BASE}/scenarios/02_i695_congestion_pricing/gps_sim/input"
os.makedirs(GPS_IN, exist_ok=True)

cand = pd.read_parquet(f"{CACHE}/gps_candidates.parquet").reset_index(drop=True)
traj = pd.read_parquet(f"{CACHE}/gps_i95_traj.parquet")
used = sorted(traj.trip.unique())
sub = cand.loc[used]
print(f"writing {len(sub)} GPS-derived I-95 plans")

def hms(sod):
    sod = int(sod) % 86400
    return f"{sod//3600:02d}:{(sod%3600)//60:02d}:{sod%60:02d}"

out = f"{GPS_IN}/gps_i95_plans.xml.gz"
with gzip.open(out, "wt") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<!DOCTYPE population SYSTEM "http://www.matsim.org/files/dtd/population_v6.dtd">\n')
    f.write('<population>\n')
    for i, r in sub.iterrows():
        f.write(f'  <person id="gps{i}">\n    <plan selected="yes">\n')
        f.write(f'      <activity type="home" x="{r.ox:.1f}" y="{r.oy:.1f}" end_time="{hms(r.dep_sod)}" />\n')
        f.write('      <leg mode="car" />\n')
        f.write(f'      <activity type="work" x="{r.dx:.1f}" y="{r.dy:.1f}" />\n')
        f.write('    </plan>\n  </person>\n')
    f.write('</population>\n')
print("wrote", out)

# minimal config referencing the base network + these plans (single mobsim pass)
cfg = f"{GPS_IN}/config_gps_sim.xml"
with open(cfg, "w") as f:
    f.write('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">
<config>
  <module name="global">
    <param name="coordinateSystem" value="EPSG:26985" />
    <param name="numberOfThreads" value="8" />
  </module>
  <module name="network">
    <param name="inputNetworkFile" value="../../output_base/base_hybrid/output_network.xml.gz" />
  </module>
  <module name="plans">
    <param name="inputPlansFile" value="gps_i95_plans.xml.gz" />
  </module>
  <module name="controler">
    <param name="outputDirectory" value="../output/matsim_run" />
    <param name="firstIteration" value="0" />
    <param name="lastIteration" value="0" />
    <param name="mobsim" value="qsim" />
    <param name="writeEventsInterval" value="1" />
  </module>
  <module name="qsim">
    <param name="startTime" value="00:00:00" />
    <param name="endTime" value="30:00:00" />
    <param name="flowCapacityFactor" value="1.0" />
    <param name="storageCapacityFactor" value="1.0" />
  </module>
  <module name="scoring">
    <parameterset type="activityParams">
      <param name="activityType" value="home" />
      <param name="typicalDuration" value="12:00:00" />
    </parameterset>
    <parameterset type="activityParams">
      <param name="activityType" value="work" />
      <param name="typicalDuration" value="08:00:00" />
    </parameterset>
    <parameterset type="modeParams"><param name="mode" value="car" /></parameterset>
  </module>
  <module name="replanning">
    <parameterset type="strategysettings">
      <param name="strategyName" value="BestScore" /><param name="weight" value="1.0" />
    </parameterset>
  </module>
</config>
''')
print("wrote", cfg)
