import asyncio
import json
import app.services.audit_runner as audit_runner

async def mock_fetch_html(url, timeout):
    return "<html><head><title>Test</title></head><body><img src='foo.jpg' /><button>Click click click</button><h2>A heading</h2></body></html>"

audit_runner._fetch_html = mock_fetch_html

async def main():
    url = "https://example.com"
    res = await audit_runner.run_audit(url, scan_mode='fast', precision_profile="balanced")
    print("\n--- RESULTS ---")
    for i in res['issues']:
        print(f"{i['rule_id']} - type:{i['issue_type']} - conf:{i['confidence']} - src:{i['confidence_sources']}")

asyncio.run(main())
