import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath('.'))

import app.services.audit_runner as ar


async def main(idx: int = 0, profile: str = 'production', scan_mode: str = 'fast'):
    with open('evaluation/benchmark_cases_20.json', encoding='utf-8') as f:
        case = json.load(f)['cases'][idx]

    original = ar._apply_precision_profile

    def passthrough(issues, profile_name):
        print(f"pre-filter issues: {len(issues)}")
        for issue in issues[:20]:
            print(' ', issue.get('rule_id'), issue.get('confidence'), issue.get('issue_type'))
        telemetry = {
            'profile': profile_name,
            'input_issues': len(issues),
            'reported_issues': len(issues),
            'dropped_low_confidence': 0,
            'dropped_needs_review': 0,
            'dropped_contextual_single_source': 0,
            'dropped_excluded_rules': 0,
            'dropped_cooccurrence_rules': 0,
            'dropped_structural': 0,
            'structural_rules_suppressed': {},
            'suppression_rate': 0.0,
            'suppression_warning': False,
            'low_issue_guard_active': False,
            'estimated_precision_floor': 0.0,
        }
        return issues, telemetry

    ar._apply_precision_profile = passthrough
    try:
        result = await ar.run_audit(
            case['url'],
            scan_mode=scan_mode,
            precision_profile=profile,
            enable_enrichment=False,
            enable_cognitive=False,
        )
    finally:
        ar._apply_precision_profile = original

    print('final issues', len(result.get('issues', [])))
    print([i.get('rule_id') for i in result.get('issues', [])[:20]])


if __name__ == '__main__':
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    profile = sys.argv[2] if len(sys.argv) > 2 else 'production'
    scan_mode = sys.argv[3] if len(sys.argv) > 3 else 'fast'
    asyncio.run(main(idx, profile, scan_mode))
