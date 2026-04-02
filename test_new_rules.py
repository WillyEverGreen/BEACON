import asyncio
import json
from app.services.audit_runner import run_audit

async def test():
    mode = "deep"
    url = "file:///d:/HACKATHON/DJ HACK/tests/wcag_22_suite.html"
    result = await run_audit(url, scan_mode=mode)
    
    issues = result.get("issues", [])
    found_rules = [issue.get("rule_id") for issue in issues]
    
    with open("tests/test_results.json", "w") as f:
        json.dump({"found": found_rules, "issues": issues}, f, indent=2)

if __name__ == "__main__":
    asyncio.run(test())
