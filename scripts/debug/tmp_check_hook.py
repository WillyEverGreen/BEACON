import asyncio
import app.services.audit_runner as ar


def spy(issues, profile_name):
    print('SPY CALLED', len(issues), profile_name)
    return issues, {
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

print('before', ar.run_audit.__globals__['_apply_precision_profile'].__name__)
ar._apply_precision_profile = spy
print('after', ar.run_audit.__globals__['_apply_precision_profile'].__name__)

async def main():
    r = await ar.run_audit(
        'https://act-rules.github.io/testcases/5f99a7/9a417788dfd68b83820b01deb71e427f8d8edc3a.html',
        scan_mode='deep',
        precision_profile='production',
        enable_enrichment=False,
        enable_cognitive=False,
        use_cache=False,
    )
    print('done', len(r.get('issues', [])))

asyncio.run(main())
