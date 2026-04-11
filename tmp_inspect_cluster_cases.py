import json
from pathlib import Path

path = Path("evaluation/retest_act_before_mapping_fix.json")
d = json.loads(path.read_text(encoding="utf-8"))

focus = {
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
}

for case in d.get("cases", []):
    if case.get("skipped"):
        continue
    expected = set(case.get("expected_rule_ids", []) or [])
    missing = set(case.get("missing_rule_ids", []) or [])
    predicted = set(case.get("predicted_rule_ids", []) or [])

    if not (expected | missing | predicted) & focus:
        continue

    print("\nCASE", case.get("name"), case.get("url"))
    print(" expected:", sorted(expected & focus))
    print(" predicted:", sorted(predicted & focus))
    print(" missing:", sorted(missing & focus))
