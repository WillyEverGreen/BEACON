"""Create a better-balanced 20-case subset for faster iteration."""
import json
import random

random.seed(42)

d = json.load(open('evaluation/benchmark_cases.json'))
cases = d['cases']

# Group by ACT rule 
from collections import defaultdict
by_act = defaultdict(list)
for c in cases:
    # Get ACT rule from URL
    url = c.get('url', '')
    parts = url.split('/testcases/')
    if len(parts) > 1:
        act_id = parts[1].split('/')[0]
        by_act[act_id].append(c)

# Select diverse cases: 1 from each of top-performing rule categories
# Focus on rules our engine CAN detect: ARIA, labels, lang, headings, etc.
priority_acts = [
    'bc4a75',  # aria-required-parent/children  
    'e086e5',  # missing-label
    'b5c3f8',  # no-lang
    '5f99a7',  # no-headings
    '1a02b0',  # no-title
    '59796f',  # button-name
    '047fe0',  # empty-heading
    '5effbb',  # empty-link
    '4e8ab6',  # aria-role
    '674b10',  # aria-valid-attr-value
    '0ssw9k',  # keyboard-trap
    'ebe86a',  # keyboard-trap
    '80af7b',  # keyboard-trap
    '0va7u6',  # semantic-html
    '23a2a8',  # svg-no-accessible-name
    'b49b2e',  # empty-heading
    'c487ae',  # empty-link
    'ye5d6e',  # focus-management (keep 2)
    'ffd0e9',  # empty-heading
    'aizyf1',  # empty-link
]

selected = []
for act_id in priority_acts:
    if act_id in by_act and len(selected) < 20:
        selected.append(random.choice(by_act[act_id]))

print(f"Selected {len(selected)} cases")
for i, c in enumerate(selected):
    print(f"  {i+1}. {c['name']}: expected={c.get('expected_rule_ids')}")

output = {"benchmark_name": "balanced_20_subset", "cases": selected}
with open('evaluation/benchmark_cases_20.json', 'w') as f:
    json.dump(output, f, indent=2)
print("\nSaved to evaluation/benchmark_cases_20.json")
