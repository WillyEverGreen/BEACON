import json
import glob
import os

print("candidate_file_case_counts:")
for f in sorted(glob.glob("evaluation/*.json")):
    base = os.path.basename(f).lower()
    if not any(k in base for k in ("act", "case", "bench")):
        continue
    try:
        data = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        print(f"{f}: {len(data['cases'])}")
