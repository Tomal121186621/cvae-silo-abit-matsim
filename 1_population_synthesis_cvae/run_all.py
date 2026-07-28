#!/usr/bin/env python3
"""Run the full Updated VAE pipeline, steps 00 → 07, in order."""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = ["00_analyze_raw_acs.py", "01_preprocess.py", "02_build_targets.py",
         "03_train.py", "04_generate.py", "05_workplace.py", "06_silo_export.py",
         "07_validate.py"]
extra = sys.argv[1:]  # forwarded to 03_train (e.g., --epochs 150)

for s in STEPS:
    print(f"\n{'='*70}\nRUN {s}\n{'='*70}", flush=True)
    args = extra if s == "03_train.py" else []
    r = subprocess.run([sys.executable, str(ROOT / "steps" / s), *args])
    if r.returncode != 0:
        print(f"FAILED at {s}"); sys.exit(r.returncode)
print("\nALL STEPS COMPLETE.")
