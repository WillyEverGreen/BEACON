#!/usr/bin/env python3
"""
Auto-generate ACT rule mapping draft from ACT rules page.

Fetches ACT rules, performs heuristic name matching against internal rule IDs,
and outputs a draft mapping with confidence scores for manual review.

Usage:
    python auto_generate_act_mapping.py \
        --act-rules https://act-rules.github.io/rules/ \
        --unmapped-report evaluation/benchmark_ingestion_report.json \
        --internal-rules app/config.py \
        --out evaluation/act_mapping_draft.json \
        --summary evaluation/act_mapping_summary.json
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional
from urllib.request import urlopen
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from collections import defaultdict


# Known internal rule IDs from codebase (extracted from config + common patterns)
INTERNAL_RULE_IDS = {
    # Link-related
    "empty-link",
    "missing-link-name",
    "link-purpose",
    "unsafe-external-link",
    
    # Image/Alt text
    "missing-alt",
    "empty-alt",
    "image-alt",
    "svg-missing-title",
    "svg-no-accessible-name",
    
    # Form
    "missing-label",
    "form-label-missing",
    "form-field-name",
    "button-no-name",
    "button-name",
    "form-error",
    
    # Heading
    "no-headings",
    "missing-heading",
    "heading-name",
    "heading-hierarchy",
    "empty-heading",
    
    # Language
    "missing-lang-attr",
    "no-lang",
    "invalid-lang",
    
    # Title/Page
    "no-title",
    "empty-title",
    
    # ARIA
    "aria-attribute",
    "aria-role",
    "aria-required-attr",
    "aria-required-parent",
    "aria-required-children",
    "invalid-aria-role",
    "aria-valid-attr-value",
    
    # Keyboard/Focus
    "keyboard-trap",
    "no-keyboard",
    "focus-visible",
    "focus-management",
    
    # Color/Contrast
    "low-contrast",
    "color-contrast",
    
    # Video/Audio/Media
    "video-caption",
    "video-transcript",
    "audio-transcript",
    "media-alternative",
    
    # Table
    "table-header",
    "table-caption",
    "table-scope",
    
    # Landmark
    "no-main-landmark",
    "main-landmark",
    
    # Structural
    "semantic-html",
    "proper-nesting",
    "duplicate-id",
    "unique-id",
    
    # Text spacing
    "text-spacing",
    "line-height",
    "letter-spacing",
    
    # Misc
    "meta-refresh",
    "parsing-error",
    "skip-nav",
    "bypass-blocks",
}


def fetch_act_rules() -> dict[str, dict]:
    """Fetch ACT rules from official page and parse."""
    print("Fetching ACT rules from https://act-rules.github.io/rules/...")
    
    # Try to parse from page
    url = "https://act-rules.github.io/rules/"
    rules = {}
    
    try:
        with urlopen(url, timeout=30) as response:
            html = response.read()
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract rule links - format: [RULE_ID: RULE_NAME](https://act-rules.github.io/rules/HASH)
        for link in soup.find_all("a", href=re.compile(r"/rules/[a-f0-9]{6}$")):
            href = link.get("href", "")
            match = re.search(r"/rules/([a-f0-9]{6})$", href)
            if match:
                rule_hash = match.group(1)
                rule_name = link.get_text(strip=True)
                rules[rule_hash] = {"name": rule_name, "url": f"https://act-rules.github.io{href}"}
        
        print(f"✓ Fetched {len(rules)} ACT rules from page")
        return rules
        
    except Exception as e:
        print(f"⚠ Failed to fetch ACT page: {e}")
        # Fallback: return empty dict, will be supplemented by test cases
        return {}


def load_unmapped_hashes(report_path: Path) -> set[str]:
    """Load unmapped ACT hashes from ingestion report."""
    if not report_path.exists():
        print(f"⚠ Report file not found: {report_path}")
        return set()
    
    with open(report_path) as f:
        report = json.load(f)
    
    # Extract unmapped count from nested source stats
    unmapped_count = 0
    for source in report.get("sources", []):
        if source.get("id") == "act_testcases":
            stats = source.get("stats", {})
            unmapped_count = stats.get("unmapped_hashes", 0)
            print(f"✓ Found {unmapped_count} unmapped ACT hashes in report")
    
    # Fallback: look for top-level field
    unmapped = set(report.get("unmapped_hashes", []))
    if unmapped:
        print(f"✓ Loaded {len(unmapped)} unmapped hashes from report field")
        return unmapped
    
    if unmapped_count > 0:
        # Return marker set - actual hashes come from test cases
        return set([f"unmapped_{i}" for i in range(unmapped_count)])
    
    print(f"⚠ No unmapped hashes found in report")
    return set()


def extract_unmapped_rules_from_testcases(
    testcases_path: Path,
    existing_mapping: dict[str, list[str]]
) -> dict[str, str]:
    """Extract unmapped ACT rules from testcases.json."""
    unmapped = {}
    
    if not testcases_path.exists():
        print(f"⚠ Testcases file not found: {testcases_path}")
        return unmapped
    
    print(f"Loading ACT testcases from {testcases_path}...")
    with open(testcases_path, encoding="utf-8", errors="ignore") as f:
        try:
            data = json.load(f)
            testcases = data.get("testcases", []) if isinstance(data, dict) else []
            
            for tc in testcases:
                rule_id = tc.get("ruleId", "")
                rule_name = tc.get("ruleName", "")
                
                if rule_id and rule_name and rule_id not in existing_mapping:
                    unmapped[rule_id] = rule_name
            
            print(f"✓ Found {len(unmapped)} unmapped rule IDs in testcases")
        except json.JSONDecodeError as e:
            print(f"⚠ Failed to parse testcases: {e}")
    
    return unmapped


def heuristic_match_rules(
    act_name: str,
    internal_ids: set[str],
    existing_mapping: dict[str, list[str]]
) -> tuple[list[str], str, bool]:
    """
    Match ACT rule name to internal rule IDs using heuristic word matching.
    
    Returns:
        (suggested_ids, confidence_level, needs_review)
    """
    
    # Normalize ACT name: lowercase, split into words
    act_words = re.findall(r"\b[a-z]+\b", act_name.lower())
    if not act_words:
        return [], "low", True
    
    # Score each internal ID
    scores: dict[str, float] = defaultdict(float)
    
    for internal_id in internal_ids:
        internal_words = re.findall(r"\b[a-z]+\b", internal_id)
        
        # Count matching words (normalized Jaccard similarity)
        common = set(act_words) & set(internal_words)
        union = set(act_words) | set(internal_words)
        
        if union:
            similarity = len(common) / len(union)
            scores[internal_id] = similarity
    
    if not scores:
        return [], "low", True
    
    # Sort by score descending
    sorted_matches = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    # Select candidates: score >= 0.5 (at least 50% word overlap)
    high_confidence = [m[0] for m in sorted_matches if m[1] >= 0.6]
    medium_confidence = [m[0] for m in sorted_matches if 0.4 <= m[1] < 0.6]
    
    # Determine overall confidence
    if high_confidence:
        suggested = high_confidence[:2]  # Top 2 high-confidence matches
        confidence = "high"
        needs_review = False
    elif medium_confidence:
        suggested = medium_confidence[:2]
        confidence = "medium"
        needs_review = True
    else:
        # Check if there's any non-zero match at all
        if sorted_matches:
            suggested = [sorted_matches[0][0]]
            confidence = "low"
            needs_review = True
        else:
            suggested = []
            confidence = "low"
            needs_review = True
    
    return suggested, confidence, needs_review


def load_act_test_cases(act_testcases_path: Path) -> dict[str, str]:
    """Load ACT rule hashes and names from test case JSON."""
    hashes = {}
    
    if not act_testcases_path.exists():
        return hashes
    
    with open(act_testcases_path, encoding="utf-8", errors="ignore") as f:
        try:
            data = json.load(f)
            if isinstance(data, dict) and "testcases" in data:
                for tc in data.get("testcases", []):
                    if "ruleId" in tc and "ruleName" in tc:
                        hashes[tc["ruleId"]] = tc["ruleName"]
        except json.JSONDecodeError:
            pass
    
    return hashes


def generate_mapping_draft(
    unmapped_hashes: set[str],
    act_rules: dict[str, dict],
    existing_mapping: dict[str, list[str]],
    act_testcases: dict[str, str]
) -> dict[str, dict]:
    """Generate draft mapping with suggestions and confidence."""
    
    draft = {}
    summary = {"high": 0, "medium": 0, "low": 0, "no_suggestion": 0}
    
    print(f"\nGenerating heuristic suggestions for {len(unmapped_hashes)} unmapped hashes...")
    
    for i, hash_id in enumerate(sorted(unmapped_hashes), 1):
        # Get rule name from ACT rules or test cases
        if hash_id in act_rules:
            rule_name = act_rules[hash_id].get("name", "Unknown")
        elif hash_id in act_testcases:
            rule_name = act_testcases[hash_id]
        else:
            rule_name = f"Unknown rule {hash_id}"
        
        # Skip if already manually mapped
        if hash_id in existing_mapping:
            continue
        
        # Generate suggestions
        suggested_ids, confidence, needs_review = heuristic_match_rules(
            rule_name,
            INTERNAL_RULE_IDS,
            existing_mapping
        )
        
        summary[confidence] += 1
        
        draft[hash_id] = {
            "act_name": rule_name,
            "act_url": act_rules.get(hash_id, {}).get("url", ""),
            "suggested_internal_ids": suggested_ids,
            "confidence": confidence,
            "needs_review": needs_review,
        }
        
        if i % 100 == 0:
            print(f"  Processed {i}/{len(unmapped_hashes)}...")
    
    print(f"✓ Generated suggestions for {len(draft)} unmapped hashes")
    print(f"  High confidence: {summary['high']}")
    print(f"  Medium confidence: {summary['medium']}")
    print(f"  Low confidence: {summary['low']}")
    
    return draft, summary


def extract_internal_rules_from_config(config_path: Path) -> set[str]:
    """Extract rule IDs from config.py."""
    rules = set()
    
    if not config_path.exists():
        return INTERNAL_RULE_IDS
    
    with open(config_path) as f:
        content = f.read()
    
    # Look for RULE_TYPE_MAP dictionary
    match = re.search(r"RULE_TYPE_MAP\s*=\s*\{([^}]+)\}", content, re.DOTALL)
    if match:
        rule_dict = match.group(1)
        # Extract quoted strings
        rule_ids = re.findall(r'"([^"]+)"\s*:', rule_dict)
        rules.update(rule_ids)
    
    # Add fallback
    if not rules:
        rules = INTERNAL_RULE_IDS
    
    return rules


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-generate ACT rule mapping draft")
    parser.add_argument(
        "--unmapped-report",
        type=Path,
        default=Path("evaluation/benchmark_ingestion_report.json"),
        help="Path to ingestion report with unmapped hashes"
    )
    parser.add_argument(
        "--internal-rules",
        type=Path,
        default=Path("app/config.py"),
        help="Path to config file with internal rule IDs"
    )
    parser.add_argument(
        "--existing-mapping",
        type=Path,
        default=Path("evaluation/act_rule_mapping.json"),
        help="Path to existing mapping (to skip already-mapped hashes)"
    )
    parser.add_argument(
        "--act-testcases",
        type=Path,
        default=Path("corpus/act/testcases.json"),
        help="Path to ACT testcases.json file"
    )
    parser.add_argument(
        "--out-draft",
        type=Path,
        default=Path("evaluation/act_mapping_draft.json"),
        help="Output path for draft mapping with suggestions"
    )
    parser.add_argument(
        "--out-summary",
        type=Path,
        default=Path("evaluation/act_mapping_summary.json"),
        help="Output path for summary statistics"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("AUTO-GENERATE ACT RULE MAPPING DRAFT")
    print("=" * 70)
    
    # Load data
    existing_mapping = {}
    if args.existing_mapping.exists():
        with open(args.existing_mapping) as f:
            existing_mapping = json.load(f) or {}
        print(f"✓ Loaded {len(existing_mapping)} existing mappings")
    
    internal_ids = extract_internal_rules_from_config(args.internal_rules)
    print(f"✓ Loaded {len(internal_ids)} internal rule IDs")
    
    # Load unmapped rules directly from testcases
    unmapped_rules = extract_unmapped_rules_from_testcases(args.act_testcases, existing_mapping)
    
    if not unmapped_rules:
        print("⚠ No unmapped rules found. Check that corpus/act/testcases.json exists.")
        print("  Trying alternative: load from benchmark_ingestion_report...")
        _ = load_unmapped_hashes(args.unmapped_report)
        return
    
    # Fetch ACT rules from web (optional - mainly for URLs)
    print("\nFetching ACT metadata from web...")
    act_rules = fetch_act_rules()
    
    # Merge with loaded testcase rules
    for hash_id, name in unmapped_rules.items():
        if hash_id not in act_rules:
            act_rules[hash_id] = {"name": name}
    
    print(f"✓ Total ACT rules available for mapping: {len(act_rules)}")
    
    # Generate draft for unmapped rules
    print(f"\nGenerating heuristic suggestions...")
    draft = {}
    summary = {"high": 0, "medium": 0, "low": 0}
    
    for hash_id in sorted(unmapped_rules.keys()):
        rule_name = unmapped_rules[hash_id]
        
        # Generate suggestions
        suggested_ids, confidence, needs_review = heuristic_match_rules(
            rule_name,
            internal_ids,
            existing_mapping
        )
        
        summary[confidence] += 1
        
        draft[hash_id] = {
            "act_name": rule_name,
            "act_url": act_rules.get(hash_id, {}).get("url", ""),
            "suggested_internal_ids": suggested_ids,
            "confidence": confidence,
            "needs_review": needs_review,
        }
    
    print(f"✓ Generated suggestions for {len(draft)} unmapped hashes")
    print(f"  High confidence: {summary['high']}")
    print(f"  Medium confidence: {summary['medium']}")
    print(f"  Low confidence: {summary['low']}")
    
    # Categorize for easy review
    high_conf = {k: v for k, v in draft.items() if v["confidence"] == "high"}
    medium_conf = {k: v for k, v in draft.items() if v["confidence"] == "medium"}
    low_conf = {k: v for k, v in draft.items() if v["confidence"] == "low"}
    
    # Save draft with categories
    output_draft = {
        "metadata": {
            "total_unmapped": len(unmapped_rules),
            "existing_mapped": len(existing_mapping),
            "suggestions_generated": len(draft),
            "high_confidence_count": len(high_conf),
            "medium_confidence_count": len(medium_conf),
            "low_confidence_count": len(low_conf),
        },
        "high_confidence": high_conf,
        "medium_confidence": medium_conf,
        "low_confidence": low_conf,
    }
    
    args.out_draft.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_draft, "w") as f:
        json.dump(output_draft, f, indent=2)
    print(f"\n✓ Draft mapping saved: {args.out_draft}")
    print(f"  {len(high_conf)} high-confidence suggestions (ready to auto-accept)")
    print(f"  {len(medium_conf)} medium-confidence suggestions (manual review recommended)")
    print(f"  {len(low_conf)} low-confidence suggestions (manual review needed)")
    
    # Save summary
    summary_output = {
        "total_unmapped": len(unmapped_rules),
        "suggestions_generated": len(draft),
        "existing_mappings": len(existing_mapping),
        "confidence_distribution": {
            "high": len(high_conf),
            "medium": len(medium_conf),
            "low": len(low_conf),
        },
        "review_effort_estimate": {
            "auto_accept_high": len(high_conf),
            "manual_review_medium": len(medium_conf),
            "manual_investigation_low": len(low_conf),
            "total_review_items": len(medium_conf) + len(low_conf),
        },
        "next_steps": [
            f"1. Review {len(high_conf)} high-confidence suggestions for auto-acceptance",
            f"2. Manually adjudicate {len(medium_conf)} medium-confidence suggestions",
            f"3. Investigate {len(low_conf)} low-confidence suggestions (may create new rule types)",
            "4. Run benchmark again with expanded mapping to measure impact",
        ]
    }
    
    args.out_summary.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_summary, "w") as f:
        json.dump(summary_output, f, indent=2)
    print(f"✓ Summary saved: {args.out_summary}")
    
    print("\n" + "=" * 70)
    print("MAPPING GENERATION COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    for step in summary_output["next_steps"]:
        print(step)


if __name__ == "__main__":
    main()
