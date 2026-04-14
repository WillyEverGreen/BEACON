import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath('.'))

from evaluation.benchmark_precision_recall import _run_all
import app.services.audit_runner as ar


async def main():
    with open('evaluation/benchmark_cases_20.json', encoding='utf-8') as f:
        benchmark = json.load(f)

    original_apply = ar._apply_precision_profile

    def passthrough(issues, profile_name):
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
        results = await _run_all(benchmark, profile='production', scan_mode='fast')
    finally:
        ar._apply_precision_profile = original_apply

    micro = results.get('aggregate', {}).get('micro', {})
    adj = results.get('aggregate', {}).get('adjudicated_micro', {})

    print('UNFILTERED ESTIMATE')
    print(f"micro precision={micro.get('precision')} recall={micro.get('recall')} f1={micro.get('f1')} tp={micro.get('tp')} fp={micro.get('fp')} fn={micro.get('fn')}")
    print(f"adj precision={adj.get('precision')} recall={adj.get('recall')} f1={adj.get('f1')}")


if __name__ == '__main__':
    asyncio.run(main())
