import json
from pathlib import Path

mapping = json.loads(Path("evaluation/act_rule_mapping.json").read_text(encoding="utf-8"))
errors = []

label_group = ["missing-label", "input-label", "form-label-missing", "label", "input-name"]
label_set = set(label_group)
for k in label_group:
    vals = set(mapping.get(k, []))
    if vals != label_set:
        errors.append(f"label mismatch {k}: {sorted(vals)}")

expected_spacing = {
    "text-spacing": ["text-spacing"],
    "letter-spacing": ["letter-spacing", "avoid-inline-spacing"],
    "avoid-inline-spacing": ["letter-spacing", "avoid-inline-spacing"],
    "line-height": ["line-height"],
}
for k, exp in expected_spacing.items():
    vals = mapping.get(k, [])
    if vals != exp:
        errors.append(f"spacing mismatch {k}: {vals}")

expected_media = {
    "media-alternative": ["media-alternative", "video-transcript"],
    "video-transcript": ["media-alternative", "video-transcript"],
    "missing-captions": ["missing-captions"],
}
for k, exp in expected_media.items():
    vals = mapping.get(k, [])
    if vals != exp:
        errors.append(f"media mismatch {k}: {vals}")

if mapping.get("semantic-html", []) != ["semantic-html"]:
    errors.append(f"semantic-html mismatch: {mapping.get('semantic-html', [])}")

expected_svg = {
    "svg-no-accessible-name": ["svg-no-accessible-name"],
    "svg-accessible-name": ["svg-accessible-name"],
    "svg-nav-accessible-name": ["svg-nav-accessible-name"],
}
for k, exp in expected_svg.items():
    vals = mapping.get(k, [])
    if vals != exp:
        errors.append(f"svg mismatch {k}: {vals}")

# Allowed bidirectional pair checks
for a, b in [("letter-spacing", "avoid-inline-spacing"), ("media-alternative", "video-transcript")]:
    if b in mapping.get(a, []) and a not in mapping.get(b, []):
        errors.append(f"asymmetric allowed pair {a}->{b}")
    if a in mapping.get(b, []) and b not in mapping.get(a, []):
        errors.append(f"asymmetric allowed pair {b}->{a}")

print("VALIDATION_ERRORS", len(errors))
for e in errors:
    print("ERR", e)

print("TOTAL_KEYS", len(mapping))
print("TOTAL_CONNECTIONS", sum(len(v) for v in mapping.values()))
