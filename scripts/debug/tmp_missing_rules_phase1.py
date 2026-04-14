import collections
import json
from pathlib import Path

path = Path("evaluation/phase12_post_upgrade_full1134_v5.json")
with path.open("r", encoding="utf-8") as f:
    r = json.load(f)

miss = collections.Counter()
for c in r.get("cases", []):
    if not c.get("skipped"):
        miss.update(c.get("missing_rule_ids", []))

print("Top Missing Rules:")
for rule_id, count in miss.most_common(25):
    print(f"{rule_id}\t{count}")

print("TOTAL_MISSING", sum(miss.values()))
