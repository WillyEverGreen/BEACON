import asyncio, json, logging
import app.services.audit_runner as ar

logging.basicConfig(level=logging.DEBUG)

async def main():
    d = json.load(open('evaluation/benchmark_cases_20.json'))
    url = d['cases'][1]['url']
    print(f"URL: {url}")
    
    orig_apply = ar._apply_precision_profile
    def fake_apply(issues, profile_name):
        print(f"INPUT ISSUES = {len(issues)}")
        for i in issues:
            print(f"  {i['rule_id']} - conf: {i.get('confidence',0):.2f}")
        return issues, orig_apply(issues, profile_name)[1]
    ar._apply_precision_profile = fake_apply
    
    res = await ar.run_audit(url, 'deep', precision_profile='production', enable_enrichment=False, enable_cognitive=False)

if __name__ == '__main__':
    asyncio.run(main())
