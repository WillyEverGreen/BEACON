#!/usr/bin/env python3
import json

with open('evaluation/act_mapping_draft.json') as f:
    draft = json.load(f)

meta = draft['metadata']
print("Summary:")
print(f"  Total unmapped: {meta['total_unmapped']}")
print(f"  High confidence: {meta['high_confidence_count']}")
print(f"  Medium confidence: {meta['medium_confidence_count']}")
print(f"  Low confidence: {meta['low_confidence_count']}")

if draft['medium_confidence']:
    print("\nMedium confidence suggestions:")
    for hash_id, suggestion in list(draft['medium_confidence'].items())[:5]:
        print(f"  {hash_id}: {suggestion['act_name']}")
        print(f"    -> {suggestion['suggested_internal_ids']}")

if draft['low_confidence']:
    print("\nLow confidence suggestions (sample 3):")
    for hash_id, suggestion in list(draft['low_confidence'].items())[:3]:
        print(f"  {hash_id}: {suggestion['act_name']}")
        print(f"    -> {suggestion['suggested_internal_ids']}")
