#!/usr/bin/env python3
"""
Merge auto-generated mapping suggestions into the main mapping.
Auto-accepts high and medium confidence suggestions.
"""

import json
from pathlib import Path


def merge_mappings():
    draft_path = Path("evaluation/act_mapping_draft.json")
    mapping_path = Path("evaluation/act_rule_mapping.json")
    
    # Load draft
    with open(draft_path) as f:
        draft = json.load(f)
    
    # Load existing mapping
    with open(mapping_path) as f:
        existing = json.load(f) or {}
    
    # Extract high + medium confidence
    high_conf = draft.get("high_confidence", {})
    medium_conf = draft.get("medium_confidence", {})
    low_conf = draft.get("low_confidence", {})
    
    # Merge high and medium confidence
    merged_count = 0
    for rule_id, suggestion in {**high_conf, **medium_conf}.items():
        suggested_ids = suggestion.get("suggested_internal_ids", [])
        if suggested_ids and rule_id not in existing:
            existing[rule_id] = suggested_ids
            merged_count += 1
            print(f"  Added: {rule_id} -> {suggested_ids}")
    
    # Save expanded mapping
    with open(mapping_path, "w") as f:
        json.dump(existing, f, indent=2)
    
    # Report
    print(f"\nMerge complete:")
    print(f"  High confidence merged: {len(high_conf)}")
    print(f"  Medium confidence merged: {len(medium_conf)}")
    print(f"  Total rules in mapping: {len(existing)}")
    print(f"  Low confidence (investigate manually): {len(low_conf)}")
    
    # Save low confidence for manual review
    with open(Path("evaluation/act_mapping_low_confidence.json"), "w") as f:
        json.dump(low_conf, f, indent=2)
    
    print(f"\nOutput files:")
    print(f"  - {mapping_path}: Updated with merged suggestions")
    print(f"  - evaluation/act_mapping_low_confidence.json: For manual review")


if __name__ == "__main__":
    print("=" * 70)
    print("MERGE HIGH/MEDIUM CONFIDENCE ACT MAPPING SUGGESTIONS")
    print("=" * 70 + "\n")
    merge_mappings()
