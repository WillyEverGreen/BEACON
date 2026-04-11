import collections
import json
from pathlib import Path

candidates = [
    Path("evaluation/benchmark_results_v5_full_1134.json"),
    Path("evaluation/phase12_post_upgrade_full1134_v5.json"),
]

result_path = next((p for p in candidates if p.exists()), None)
if not result_path:
    raise SystemExit("No benchmark result file found")

mapping_path = Path("evaluation/act_rule_mapping.json")
result = json.loads(result_path.read_text(encoding="utf-8"))
mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

emitted = collections.Counter()
for case in result.get("cases", []):
    if case.get("skipped"):
        continue
    emitted.update(case.get("predicted_rule_ids", []) or [])

focus_rules = [
    "missing-label",
    "input-label",
    "form-label-missing",
    "label",
    "input-name",
    "text-spacing",
    "letter-spacing",
    "line-height",
    "avoid-inline-spacing",
    "media-alternative",
    "video-transcript",
    "missing-captions",
    "semantic-html",
    "div-itis-missing-semantics",
    "svg-no-accessible-name",
    "svg-accessible-name",
    "svg-nav-accessible-name",
]

print("RESULT_FILE", result_path.as_posix())
print("TOTAL_EMITTED_UNIQUE", len(emitted))
print("\nFOCUS_RULE_EMISSION")
for rule in focus_rules:
    print(rule, emitted.get(rule, 0))

print("\nFOCUS_MAPPING_VALUES")
for key in [
    "missing-label",
    "input-label",
    "form-label-missing",
    "label",
    "input-name",
    "text-spacing",
    "letter-spacing",
    "line-height",
    "avoid-inline-spacing",
    "media-alternative",
    "video-transcript",
    "missing-captions",
    "semantic-html",
    "div-itis-missing-semantics",
    "svg-no-accessible-name",
    "svg-accessible-name",
    "svg-nav-accessible-name",
]:
    vals = mapping.get(key, [])
    unemitted = [v for v in vals if emitted.get(v, 0) == 0]
    print(key, "=>", vals, "| unemitted:", unemitted)
