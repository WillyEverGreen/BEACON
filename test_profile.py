import asyncio
from app.services.audit_runner import run_audit
import app.config as cfg
cfg.PRECISION_PROFILES['balanced']['min_confidence'] = 0.0

async def test():
    res = await run_audit('https://act-rules.github.io/testcases/5f99a7/9a417788dfd68b83820b01deb71e427f8d8edc3a.html?11', precision_profile='balanced', scan_mode='fast')
    for i in res.get('issues', []):
        print(f"rule: {i['rule_id']}, conf={i['confidence']}, sources: {i.get('confidence_sources')}, snippet: {bool(i.get('html_snippet'))}")

asyncio.run(test())
