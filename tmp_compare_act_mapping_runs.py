import collections
import json
from pathlib import Path

before_path = Path("evaluation/retest_act_before_mapping_fix.json")
after_path = Path("evaluation/retest_act_after_mapping_fix_v3.json")

before = json.loads(before_path.read_text(encoding="utf-8"))
after = json.loads(after_path.read_text(encoding="utf-8"))


def summarize(data: dict) -> tuple[dict, collections.Counter]:
    micro = data.get("aggregate", {}).get("micro", {})
    missing = collections.Counter()
    for case in data.get("cases", []):
        if case.get("skipped"):
            continue
        missing.update(case.get("missing_rule_ids", []) or [])
    return micro, missing

bm, bmiss = summarize(before)
am, amiss = summarize(after)

print("BEFORE_MICRO", bm)
print("AFTER_MICRO", am)
print("DELTA_RECALL", round((am.get("recall", 0) - bm.get("recall", 0)) * 100, 2))
print("DELTA_PRECISION", round((am.get("precision", 0) - bm.get("precision", 0)) * 100, 2))

print("\nTOP_FN_BEFORE")
for rule, count in bmiss.most_common(15):
    print(rule, count)

print("\nTOP_FN_AFTER")
for rule, count in amiss.most_common(15):
    print(rule, count)

print("\nFN_DELTA_RULES")
for rule in sorted(set(bmiss) | set(amiss)):
    delta = amiss.get(rule, 0) - bmiss.get(rule, 0)
    if delta != 0:
        print(rule, delta, "(after-before)")
