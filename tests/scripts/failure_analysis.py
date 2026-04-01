#!/usr/bin/env python3
"""
Deep dive analysis: Why the model failed on specific issues
"""

import json
import re
from pathlib import Path

AUDIT_REPORT = "universal_audit_report.json"
LOCAL_CODEBASE = r"D:\GSOC\musicblocks"

# Load audit report
with open(AUDIT_REPORT, 'r', encoding='utf-8', errors='ignore') as f:
    audit_data = json.load(f)

# Load index.html
index_path = Path(LOCAL_CODEBASE) / "index.html"
with open(index_path, 'r', encoding='utf-8', errors='ignore') as f:
    index_content = f.read()

# Extract issues by type
issues_by_type = {}
for url, url_data in audit_data.items():
    for issue in url_data.get("issues", []):
        rule = issue.get("rule_id")
        if rule not in issues_by_type:
            issues_by_type[rule] = []
        issues_by_type[rule].append(issue)

print("="*90)
print("FAILURE ANALYSIS: Why the Model Failed")
print("="*90)
print()

# Analyze failures
failures = {
    "no-headings": issues_by_type.get("no-headings", []),
    "svg-no-accessible-name": issues_by_type.get("svg-no-accessible-name", []),
    "unsafe-external-link": issues_by_type.get("unsafe-external-link", []),
    "missing-captions": issues_by_type.get("missing-captions", []),
}

print("1. NO-HEADINGS (1 issue reported, 0 found)")
print("-" * 90)
if failures.get("no-headings"):
    issue = failures["no-headings"][0]
    print(f"   Audit claimed: {issue.get('description')}")
    print(f"   Element: {issue.get('element')}")
    print(f"   HTML snippet: {issue.get('html_snippet')[:100]}")
    print()
    
    # Check what we actually found
    headings = re.findall(r'<h[1-6][^>]*>.*?</h[1-6]>', index_content, re.DOTALL)
    print(f"   Reality check: Found {len(headings)} heading elements in index.html")
    for i, h in enumerate(headings[:3], 1):
        print(f"     {i}. {h[:80]}")
    if len(headings) > 3:
        print(f"     ... and {len(headings) - 3} more")
print()

print("2. SVG-NO-ACCESSIBLE-NAME (1 issue reported, 0 found)")
print("-" * 90)
if failures.get("svg-no-accessible-name"):
    issue = failures["svg-no-accessible-name"][0]
    print(f"   Audit claimed: {issue.get('description')}")
    print(f"   Element: {issue.get('element')}")
    print()
    
    # Check SVG elements
    svg_elements = re.findall(r'<svg[^>]*>.*?</svg>', index_content, re.DOTALL)
    print(f"   Reality check: Found {len(svg_elements)} SVG elements")
    
    # Check for SVGs with accessible names
    svg_with_title = len(re.findall(r'<svg[^>]*>.*?<title', index_content, re.DOTALL))
    svg_with_aria = len(re.findall(r'<svg[^>]*aria-label', index_content))
    
    print(f"     - SVG with <title>: {svg_with_title}")
    print(f"     - SVG with aria-label: {svg_with_aria}")
    print(f"     - SVG without accessible name: {len(svg_elements) - svg_with_title - svg_with_aria}")
    
    if svg_elements:
        print(f"\n   First SVG found:")
        print(f"     {svg_elements[0][:150]}...")
print()

print("3. UNSAFE-EXTERNAL-LINK (1 issue reported, 0 found)")
print("-" * 90)
if failures.get("unsafe-external-link"):
    issue = failures.get("unsafe-external-link")[0]
    print(f"   Audit claimed: {issue.get('description')}")
    print(f"   Element: {issue.get('element')}")
    print(f"   HTML snippet: {issue.get('html_snippet')[:150]}")
    print()
    
    # Check links
    external_links_blank = re.findall(r'<a[^>]*target=["\']_blank["\'][^>]*>', index_content)
    external_links_with_rel = re.findall(r'<a[^>]*target=["\']_blank["\'][^>]*rel=', index_content)
    
    print(f"   Reality check:")
    print(f"     - Links with target='_blank': {len(external_links_blank)}")
    print(f"     - Links with target='_blank' AND rel=: {len(external_links_with_rel)}")
    print(f"     - Unsafe links (target='_blank' without rel): {len(external_links_blank) - len(external_links_with_rel)}")
print()

print("4. MISSING-CAPTIONS (2 issues reported, 0 found)")
print("-" * 90)
if failures.get("missing-captions"):
    for i, issue in enumerate(failures["missing-captions"], 1):
        print(f"   Issue {i}:")
        print(f"     Element: {issue.get('element')}")
        print(f"     Description: {issue.get('description')}")
    print()
    
    # Check for video elements
    video_elements = re.findall(r'<video[^>]*>.*?</video>', index_content, re.DOTALL)
    print(f"   Reality check: Found {len(video_elements)} video elements")
    
    if video_elements:
        for i, v in enumerate(video_elements[:2], 1):
            print(f"     Video {i}: {v[:100]}...")

print()
print("="*90)
print("ROOT CAUSES OF FAILURES")
print("="*90)
print()

print("PROBLEM 1: Static HTML Analysis Limitations")
print("-" * 90)
print("The audit tool uses axe-core which runs in a browser. When it scans")
print("the LIVE website (https://musicblocks.sugarlabs.org/), it may detect")
print("dynamically rendered elements that don't exist in the static HTML source.")
print()
print("Examples:")
print("  - Headings might be injected by JavaScript")
print("  - SVG labels might be added by JavaScript")
print("  - Video elements might be dynamically created")
print()

print("PROBLEM 2: Different URLs = Different Content")
print("-" * 90)
print("Audit scanned: https://musicblocks.sugarlabs.org/ (LIVE website)")
print("We checked: D:\\GSOC\\musicblocks\\index.html (LOCAL SOURCE CODE)")
print()
print("These may be different:")
print("  - Build output vs source code")
print("  - Production version vs development version")
print("  - Transpiled/bundled code vs original")
print()

print("PROBLEM 3: CSS-based Issues Can't be Detected from HTML")
print("-" * 90)
print("10 'no-focus-style' issues cannot be verified from HTML alone.")
print("These require:")
print("  - CSS file inspection")
print("  - Browser rendering")
print("  - Visual testing")
print()

print("="*90)
print("HOW TO ACHIEVE 100% ACCURACY")
print("="*90)
print()

print("STRATEGY 1: Audit Against Production Build Output")
print("-" * 90)
print("Current: Auditing live website vs checking source code")
print("Better: Audit the BUILT output that matches the live website")
print()
print("Steps:")
print("  1. cd D:\\GSOC\\musicblocks")
print("  2. npm run build  (or equivalent)")
print("  3. Audit the dist/ folder instead of source")
print("  4. Compare against built HTML")
print()

print("STRATEGY 2: Use Headless Browser for Local Audit")
print("-" * 90)
print("Current: Static HTML regex scanning")
print("Better: Use Puppeteer/Playwright + axe-core on local files")
print()
print("Benefits:")
print("  - Renders JavaScript")
print("  - Applies CSS")
print("  - Mimics actual browser behavior")
print("  - Detects dynamically added elements")
print()

print("STRATEGY 3: Cross-validate Multiple Detection Methods")
print("-" * 90)
print("Combine:")
print("  A) Static HTML analysis (regex/parsing)")
print("  B) CSS file inspection")
print("  C) JavaScript execution")
print("  D) Headless browser rendering")
print()
print("Weight different methods based on issue type:")
print("  - empty-link: Use static HTML ✓ works 100%")
print("  - missing-label: Use static HTML ✓ works 100%")
print("  - no-focus-style: Use CSS inspection (not HTML)")
print("  - color-contrast: Use rendered output (not source)")
print()

print("STRATEGY 4: Build a Local Audit Pipeline")
print("-" * 90)
print("Instead of auditing live website:")
print("  1. Checkout specific commit from repo")
print("  2. Run build command locally")
print("  3. Start local dev server")
print("  4. Run axe-core against localhost:port")
print("  5. Cross-reference with source files")
print("  6. Track regressions")
print()

print("="*90)
print("RECOMMENDED NEXT STEPS")
print("="*90)
print()
print("1. IMMEDIATE (Quick wins for accuracy):")
print("   - Check D:\\GSOC\\musicblocks\\dist/ for built output")
print("   - Compare index.html from dist vs actual website")
print("   - Look at package.json for build commands")
print()
print("2. SHORT-TERM (Better accuracy):")
print("   - Create script to audit built output instead of live site")
print("   - Add CSS inspection to validator")
print("   - Generate separate reports for HTML vs CSS issues")
print()
print("3. LONG-TERM (100% accuracy):")
print("   - Integrate Playwright/Puppeteer for headless rendering")
print("   - Build local dev server startup for audit")
print("   - Implement multi-stage validation pipeline")
print()
