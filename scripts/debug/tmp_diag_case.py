import asyncio
import json
import sys

import app.services.audit_runner as ar


async def main(case_index: int, profile: str = 'production', scan_mode: str = 'deep'):
    with open('evaluation/benchmark_cases_20.json', encoding='utf-8') as f:
        data = json.load(f)

    case = data['cases'][case_index]
    url = case['url']
    print(f"Case {case_index}: expected={case.get('expected_rule_ids', [])}")
    print(f"URL: {url}")

    original_apply = ar._apply_precision_profile

    def spy_apply(issues, profile_name):
        print(f"\nINPUT ISSUES = {len(issues)}")
        for issue in issues:
            print(
                f"  {issue.get('rule_id')} conf={issue.get('confidence', 0):.3f} "
                f"sev={issue.get('severity')} sources={issue.get('confidence_sources', [])}"
            )
        kept, telemetry = original_apply(issues, profile_name)
        print(f"\nKEPT ISSUES = {len(kept)}")
        for issue in kept:
            print(f"  kept: {issue.get('rule_id')} conf={issue.get('confidence', 0):.3f}")
        print(f"\nTELEMETRY: {telemetry}")
        return kept, telemetry

    ar._apply_precision_profile = spy_apply

    try:
        result = await ar.run_audit(
            url,
            scan_mode=scan_mode,
            precision_profile=profile,
            enable_enrichment=False,
            enable_cognitive=False,
            use_cache=False,
        )
        print(f"\nSUMMARY: {result.get('summary')}")
        print(f"PREDICTED: {[i.get('rule_id') for i in result.get('issues', [])]}")
    finally:
        ar._apply_precision_profile = original_apply


if __name__ == '__main__':
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    profile = sys.argv[2] if len(sys.argv) > 2 else 'production'
    scan_mode = sys.argv[3] if len(sys.argv) > 3 else 'deep'
    asyncio.run(main(idx, profile, scan_mode))
