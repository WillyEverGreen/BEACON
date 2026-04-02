import asyncio
import time
import json
from collections import Counter
from app.services.audit_runner import run_audit
import warnings

# Suppress noisy warnings
warnings.filterwarnings("ignore")

URLS = [
    "https://example.com",
    "https://www.w3.org",
    "https://news.ycombinator.com",
    "https://www.wikipedia.org",
    "https://www.a11yproject.com/",
    "https://github.com",
    "https://developer.mozilla.org",
    "https://stackoverflow.com",
    "https://www.apple.com",
    "https://www.microsoft.com"
]

async def verify_real_sites():
    print("Starting Comprehensive Real-Site Benchmarks (DEEP mode)...\n" + "="*60)
    report = []
    
    for url in URLS:
        try:
            start = time.time()
            res = await run_audit(url, precision_profile="balanced", scan_mode="deep", enable_enrichment=False)
            duration = time.time() - start
            
            issues = res.get("issues", [])
            score = res.get("score", 0)
            telemetry = res.get("precision_profile_telemetry", {})
            dropped = telemetry.get('dropped_low_confidence', 0)
            
            rule_counts = Counter(i.get("rule_id", "unknown") for i in issues)
            top_rules = dict(rule_counts.most_common(3))
            
            print(f"[✓] {url}")
            print(f"    Score: {score}/100 | Issues Found: {len(issues)} | False-Positives Filtered: {dropped}")
            print(f"    Time: {duration:.2f}s | Top Violations: {top_rules}")
            print("-" * 60)
            
            report.append({
                "url": url,
                "score": score,
                "issues": len(issues),
                "filtered": dropped,
                "top_rules": top_rules
            })
        except Exception as e:
            print(f"[X] {url}")
            print(f"    FAILED: {str(e)[:100]}")
            print("-" * 60)

    with open("real_sites_validation.json", "w") as f:
        json.dump(report, f, indent=2)
    print("Validation complete.")

if __name__ == "__main__":
    import os
    if os.path.exists("app/data/page_cache.json"):
        os.remove("app/data/page_cache.json")
    asyncio.run(verify_real_sites())
