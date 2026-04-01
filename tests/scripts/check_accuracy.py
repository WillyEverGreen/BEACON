#!/usr/bin/env python3
"""
Compare audit findings against local musicblocks codebase to check model accuracy.
"""

import json
import os
from pathlib import Path
from collections import defaultdict
import re

# Paths
AUDIT_REPORT = "universal_audit_report.json"
LOCAL_CODEBASE = r"D:\GSOC\musicblocks"

def load_audit_report(filepath):
    """Load the audit report JSON."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def scan_codebase_for_issues(base_path):
    """Scan local codebase and find similar issues."""
    issues_found = {
        "headings": [],
        "alt_text": [],
        "empty_links": [],
        "unsafe_links": [],
        "semantic_html": [],
        "labels": [],
        "form_issues": [],
        "color_contrast": [],
    }
    
    # Scan HTML files
    html_files = list(Path(base_path).rglob("*.html"))
    print(f"Scanning {len(html_files)} HTML files...")
    
    for html_file in html_files[:10]:  # Check first 10 for speed
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Check for missing headings
            if '<h1>' not in content and '<h2>' not in content:
                issues_found["headings"].append(str(html_file))
            
            # Check for img without alt
            img_matches = re.findall(r'<img[^>]*?>', content)
            for img in img_matches:
                if 'alt=' not in img:
                    issues_found["alt_text"].append((str(html_file), img[:60]))
            
            # Check for empty links
            empty_links = re.findall(r'<a[^>]*href[^>]*>\s*</a>', content)
            if empty_links:
                issues_found["empty_links"].append((str(html_file), len(empty_links)))
            
            # Check for links with target="_blank" without rel
            unsafe_link_matches = re.findall(r'<a[^>]*target=["\']_blank["\'][^>]*(?!rel=)[^>]*>', content)
            for match in unsafe_link_matches:
                if 'rel=' not in match:
                    issues_found["unsafe_links"].append((str(html_file), match[:60]))
            
            # Check for SVG without accessible names
            svg_matches = re.findall(r'<svg[^>]*>(?!<title>).*?</svg>', content, re.DOTALL)
            if svg_matches:
                issues_found["semantic_html"].append((str(html_file), f'{len(svg_matches)} SVGs'))
            
            # Check for form labels
            labels_missing = re.findall(r'<input[^>]*(?!.*<label[^>]*for=)[^>]*>', content)
            if labels_missing:
                issues_found["labels"].append((str(html_file), len(labels_missing)))
        
        except Exception as e:
            print(f"Error processing {html_file}: {e}")
    
    return issues_found

def get_audit_summary(audit_data):
    """Extract summary from audit report."""
    summary = defaultdict(int)
    
    for url, data in audit_data.items():
        issues = data.get("issues", [])
        for issue in issues:
            rule_id = issue.get("rule_id", "unknown")
            severity = issue.get("severity", "unknown")
            summary[f"{rule_id}_{severity}"] += 1
    
    return summary

def calculate_accuracy_metrics(audit_data, local_issues):
    """Calculate accuracy metrics."""
    audit_summary = get_audit_summary(audit_data)
    
    print("\n" + "="*80)
    print("AUDIT REPORT FINDINGS")
    print("="*80)
    
    for key, count in sorted(audit_summary.items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f"  {key}: {count}")
    
    print("\n" + "="*80)
    print("LOCAL CODEBASE ISSUES FOUND")
    print("="*80)
    
    for issue_type, findings in local_issues.items():
        if findings:
            print(f"\n{issue_type}:")
            if isinstance(findings, list) and len(findings) > 0:
                if isinstance(findings[0], tuple):
                    for item in findings[:5]:
                        print(f"  - {item}")
                else:
                    for item in findings[:5]:
                        print(f"  - {item}")
    
    # Analysis
    print("\n" + "="*80)
    print("ACCURACY ANALYSIS")
    print("="*80)
    
    total_audit_issues = sum(audit_summary.values())
    
    # Count detected issues in local codebase
    local_detected = sum(len(v) if isinstance(v, list) else (v if isinstance(v, int) else 0) 
                        for v in local_issues.values())
    
    print(f"\nTotal audit issues found: {total_audit_issues}")
    print(f"Local codebase issues detected: {local_detected}")
    
    # Comparison
    print("\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)
    
    # Check specific issues from audit
    audit_rules = {}
    for url, data in audit_data.items():
        for issue in data.get("issues", []):
            rule = issue.get("rule_id")
            if rule:
                audit_rules[rule] = audit_rules.get(rule, 0) + 1
    
    print("\nTop issues from audit report:")
    for rule, count in sorted(audit_rules.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {rule}: {count} occurrences")
    
    # Validation
    print("\n" + "="*80)
    print("VALIDATION AGAINST LOCAL CODEBASE")
    print("="*80)
    
    # Check index.html
    index_path = os.path.join(LOCAL_CODEBASE, "index.html")
    if os.path.exists(index_path):
        print(f"\n✓ index.html exists")
        with open(index_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Check specific issues the audit reported
        print(f"  - Has <h1>: {'<h1>' in content}")
        print(f"  - Has <h2>: {'<h2>' in content}")
        print(f"  - SVG elements: {len(re.findall(r'<svg', content))}")
        blank_target_count = len(re.findall(r'target=[\"\']_blank[\"\']', content))
        print(f"  - Links with target='_blank': {blank_target_count}")
        unsafe_links = len(re.findall(r'target=[\"\']_blank[\"\'](?!.*rel=)', content))
        print(f"  - Unsafe external links: {unsafe_links}")

if __name__ == "__main__":
    print("Checking model accuracy against local musicblocks codebase...\n")
    
    # Load audit report
    if os.path.exists(AUDIT_REPORT):
        audit_data = load_audit_report(AUDIT_REPORT)
        print(f"Loaded audit report with {len(audit_data)} URLs")
    else:
        print(f"Audit report not found at {AUDIT_REPORT}")
        audit_data = {}
    
    # Scan local codebase
    if os.path.exists(LOCAL_CODEBASE):
        print(f"Scanning local codebase at {LOCAL_CODEBASE}")
        local_issues = scan_codebase_for_issues(LOCAL_CODEBASE)
    else:
        print(f"Local codebase not found at {LOCAL_CODEBASE}")
        local_issues = {}
    
    # Calculate metrics
    if audit_data and local_issues:
        calculate_accuracy_metrics(audit_data, local_issues)
    else:
        print("Unable to calculate accuracy metrics - missing data")
