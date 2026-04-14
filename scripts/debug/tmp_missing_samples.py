import collections
import json
from pathlib import Path

path = Path("evaluation/phase12_post_upgrade_full1134_v5.json")
r = json.loads(path.read_text(encoding="utf-8"))

rules = [
    "avoid-inline-spacing",
    "letter-spacing",
    "text-spacing",
    "semantic-html",
    "svg-no-accessible-name",
    "aria-valid-attr-value",
    "media-alternative",
    "keyboard-trap",
    "no-lang",
    "empty-link",
    "link-name",
    "unsafe-external-link",
    "aria-role",
    "form-label-missing",
    "input-label",
    "input-name",
    "label",
    "missing-label",
    "empty-heading",
    "link-purpose",
]

for rule in rules:
    print(f"\n=== {rule} ===")
    seen = 0
    for c in r.get("cases", []):
        if c.get("skipped"):
            continue
        missing = set(c.get("missing_rule_ids", []) or [])
        if rule not in missing:
            continue
        url = c.get("url")
        expected = c.get("expected_rule_ids", [])
        predicted = c.get("predicted_rule_ids", [])
        print("URL:", url)
        print(" expected_has:", rule in expected, "expected_count:", len(expected), "pred_count:", len(predicted))
        print(" predicted_sample:", ", ".join(predicted[:12]))
        seen += 1
        if seen >= 3:
            break
