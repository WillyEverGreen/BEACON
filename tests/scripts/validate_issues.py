#!/usr/bin/env python3
"""
Verify which of the 73 audit issues actually exist in the local musicblocks codebase.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

AUDIT_REPORT = "universal_audit_report.json"
LOCAL_CODEBASE = r"D:\GSOC\musicblocks"

# Load audit report
with open(AUDIT_REPORT, 'r', encoding='utf-8', errors='ignore') as f:
    audit_data = json.load(f)

# Extract all issues
issues = []
for url, url_data in audit_data.items():
    for issue in url_data.get("issues", []):
        issues.append(issue)

print(f"Total issues to validate: {len(issues)}\n")

# Search index.html for evidence
index_path = Path(LOCAL_CODEBASE) / "index.html"

if not index_path.exists():
    print(f"ERROR: {index_path} not found!")
    exit(1)

with open(index_path, 'r', encoding='utf-8', errors='ignore') as f:
    index_content = f.read()

# Categorize issues and check them
validation_results = defaultdict(lambda: {"found": 0, "not_found": 0, "issues": []})

for i, issue in enumerate(issues, 1):
    rule_id = issue.get("rule_id", "unknown")
    element = issue.get("element", "")
    description = issue.get("description", "")
    
    # Check based on rule_id
    found = False
    
    if rule_id == "no-headings":
        # Check if page has any headings
        found = bool(re.search(r'<h[1-6]', index_content))
        
    elif rule_id == "svg-no-accessible-name":
        # Check for SVG without title
        found = bool(re.search(r'<svg[^>]*>.*?<title', index_content, re.DOTALL)) or \
                bool(re.search(r'<svg[^>]*aria-label', index_content))
        
    elif rule_id == "empty-link":
        # Check for links with content
        found = bool(re.search(r'<a[^>]*>\s*(.+?)\s*</a>', index_content, re.DOTALL))
        
    elif rule_id == "missing-label":
        # Check for input elements with associated labels
        found = bool(re.search(r'<label[^>]*for=["\']', index_content))
        
    elif rule_id == "missing-captions":
        # Check for video elements with captions
        found = bool(re.search(r'<video[^>]*>.*?<track', index_content, re.DOTALL))
        
    elif rule_id == "unsafe-external-link":
        # Check for links with rel="noopener"
        found = bool(re.search(r'rel=["\']noopener', index_content))
        
    elif rule_id == "button-no-name":
        # Check for buttons with text/aria-label
        found = bool(re.search(r'<button[^>]*>(.+?)</button>', index_content, re.DOTALL))
        
    elif rule_id == "no-focus-style":
        # This requires CSS inspection - cannot determine from HTML
        found = None
        
    else:
        # For other rules, assume not checked
        found = None
    
    # Categorize result
    if found is True:
        validation_results[rule_id]["found"] += 1
        validation_results[rule_id]["issues"].append((i, "CONFIRMED", element[:50]))
    elif found is False:
        validation_results[rule_id]["not_found"] += 1
        validation_results[rule_id]["issues"].append((i, "NOT FOUND", element[:50]))
    else:
        validation_results[rule_id]["not_found"] += 1
        validation_results[rule_id]["issues"].append((i, "CANNOT VERIFY", element[:50]))

print("="*80)
print("VALIDATION RESULTS")
print("="*80)
print()

total_confirmed = 0
total_not_found = 0

for rule_id in sorted(validation_results.keys()):
    data = validation_results[rule_id]
    found = data["found"]
    not_found = data["not_found"]
    total_confirmed += found
    total_not_found += not_found
    
    print(f"{rule_id}:")
    print(f"  Confirmed in codebase: {found}")
    print(f"  NOT found: {not_found}")
    
    # Show details
    for issue_num, status, element in data["issues"][:3]:
        print(f"    [{status}] Issue #{issue_num}: {element}")
    
    if len(data["issues"]) > 3:
        print(f"    ... and {len(data['issues']) - 3} more")
    print()

print("="*80)
print("SUMMARY")
print("="*80)
print(f"Total issues analyzed: {len(issues)}")
print(f"Issues CONFIRMED in codebase: {total_confirmed}")
print(f"Issues NOT found in codebase: {total_not_found}")
print()

if total_confirmed > 0:
    accuracy_rate = (total_confirmed / len(issues)) * 100
    print(f"Accuracy rate: {accuracy_rate:.1f}%")
else:
    print("Accuracy rate: 0% (No issues confirmed)")

print()
print("="*80)
print("INTERPRETATION")
print("="*80)

high_false_positive_rate = (total_not_found / len(issues)) * 100
if high_false_positive_rate > 50:
    print(f"WARNING: High false positive rate ({high_false_positive_rate:.1f}%)")
    print("Many reported issues do NOT exist in the actual codebase!")
    print("The audit model may be:")
    print("  - Unable to parse JavaScript-rendered content")
    print("  - Reporting issues that exist dynamically at runtime")
    print("  - Over-detecting based on patterns")
elif high_false_positive_rate > 30:
    print(f"MODERATE: {high_false_positive_rate:.1f}% false positive rate")
    print("Several issues need manual verification")
else:
    print(f"GOOD: Only {high_false_positive_rate:.1f}% false positives")
    print("Most reported issues are likely valid")
