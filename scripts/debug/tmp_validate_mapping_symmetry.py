import json
from pathlib import Path

path = Path("evaluation/act_rule_mapping.json")
mapping = json.loads(path.read_text(encoding="utf-8"))

clusters = {
    "label": [
        "missing-label",
        "input-label",
        "form-label-missing",
        "label",
        "input-name",
    ],
    "spacing": [
        "text-spacing",
        "letter-spacing",
        "line-height",
        "avoid-inline-spacing",
    ],
    "media": [
        "media-alternative",
        "video-transcript",
        "missing-captions",
    ],
    "semantic": [
        "semantic-html",
        "div-itis-missing-semantics",
    ],
    "svg": [
        "svg-no-accessible-name",
        "svg-accessible-name",
        "svg-nav-accessible-name",
    ],
}

failures: list[tuple[str, str, str]] = []
connection_count = 0

for cluster_name, keys in clusters.items():
    for src in keys:
        neighbors = mapping.get(src, [])
        connection_count += len(neighbors)
        for dst in neighbors:
            reverse_neighbors = mapping.get(dst)
            if reverse_neighbors is None or src not in reverse_neighbors:
                failures.append((cluster_name, src, dst))

print("CLUSTER_CONNECTIONS", connection_count)
print("SYMMETRY_FAIL_COUNT", len(failures))
for item in failures[:50]:
    print("FAIL", item[0], item[1], "->", item[2])
