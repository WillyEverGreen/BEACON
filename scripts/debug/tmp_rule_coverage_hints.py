import collections
import json
from pathlib import Path

res_path = Path("evaluation/phase12_post_upgrade_full1134_v5.json")
with res_path.open("r", encoding="utf-8") as f:
    result = json.load(f)

miss = collections.Counter()
for c in result.get("cases", []):
    if not c.get("skipped"):
        miss.update(c.get("missing_rule_ids", []))

top20 = [rule for rule, _ in miss.most_common(20)]

per_rule = result.get("per_rule_metrics", {})

map_path = Path("evaluation/act_rule_mapping.json")
with map_path.open("r", encoding="utf-8") as f:
    act_map = json.load(f)

all_targets = collections.defaultdict(list)
for k, vals in act_map.items():
    for v in vals:
        all_targets[v].append(k)

search_roots = [Path("app/services"), Path("app/audit")]
py_files = []
for root in search_roots:
    if root.exists():
        py_files.extend(root.rglob("*.py"))

print("rule\tcount\ttp\tfp\tfn\tis_act_key\tmapped_targets\tmapped_from_keys\tdetector_files")
for rule in top20:
    count = miss[rule]
    m = per_rule.get(rule, {})
    tp = int(m.get("tp", 0) or 0)
    fp = int(m.get("fp", 0) or 0)
    fn = int(m.get("fn", 0) or 0)

    is_act_key = rule in act_map
    mapped_targets = act_map.get(rule, []) if is_act_key else []
    mapped_from_keys = all_targets.get(rule, [])

    detector_files = []
    token = f'"{rule}"'
    for p in py_files:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if token in txt:
            detector_files.append(str(p).replace('\\', '/'))

    print(
        f"{rule}\t{count}\t{tp}\t{fp}\t{fn}\t{is_act_key}\t"
        f"{','.join(mapped_targets[:8])}\t{','.join(mapped_from_keys[:8])}\t{','.join(detector_files[:8])}"
    )
