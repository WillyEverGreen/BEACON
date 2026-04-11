import collections
import json
from pathlib import Path

before_path = Path("evaluation/retest_act_after_mapping_fix_v3.json")
after_path = Path("evaluation/retest_act_after_mapping_hybrid_v4.json")

before = json.loads(before_path.read_text(encoding="utf-8"))
after = json.loads(after_path.read_text(encoding="utf-8"))

def summarize(data):
    micro = data.get("aggregate", {}).get("micro", {})
    missing = collections.Counter()
    fn_total = 0
    for case in data.get("cases", []):
        if case.get("skipped"):
            continue
        miss = case.get("missing_rule_ids", []) or []
        missing.update(miss)
        fn_total += len(miss)
    return micro, missing, fn_total

bm, bmiss, bfn = summarize(before)
am, amiss, afn = summarize(after)

print("BEFORE_MICRO", bm)
print("AFTER_MICRO", am)
print("DELTA_RECALL", round((am.get("recall", 0) - bm.get("recall", 0)) * 100, 2))
print("DELTA_PRECISION", round((am.get("precision", 0) - bm.get("precision", 0)) * 100, 2))
print("DELTA_F1", round((am.get("f1", 0) - bm.get("f1", 0)) * 100, 2))
print("BEFORE_FN_TOTAL", bfn)
print("AFTER_FN_TOTAL", afn)
print("DELTA_FN_TOTAL", afn - bfn)

print("\nTOP_FN_AFTER")
for rid, cnt in amiss.most_common(15):
    print(rid, cnt)
