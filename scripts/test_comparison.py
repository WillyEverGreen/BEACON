import asyncio
import time
from app.services.audit_runner import run_audit
from app.services.lighthouse_runner import run_lighthouse_for_url
from app.services.lighthouse_mapper import map_lighthouse_report
from app.services.lighthouse_enricher import merge_findings

SITES = [
    "https://nab.org.in",
    "https://sightsavers.in",
    "https://tiss.edu",
    "https://varsity.zerodha.com",
    "https://cleartax.in",
    "https://zerodha.com",
    "https://scholarships.gov.in",
    "https://practo.com",
    "https://groww.in",
    "https://diksha.gov.in",
]

async def analyze_site(url: str):
    t0 = time.monotonic()
    
    # 1. BEACON Only
    try:
        beacon_result = await run_audit(url=url, scan_mode="fast", use_cache=False)
        beacon_issues = beacon_result.get("issues", [])
    except Exception as e:
        beacon_issues = []
        
    # 2. Lighthouse
    lh_issues = []
    lh_failed = False
    try:
        lh_res = await run_lighthouse_for_url(url)
        lh_raw = lh_res.get("raw_report", {})
        if lh_raw:
            lh_issues = map_lighthouse_report(lh_raw, page_url=url)
        else:
            lh_failed = True
    except Exception as e:
        lh_failed = True
        
    # 3. Merged
    merged_issues, telemetry = merge_findings(beacon_issues, lh_issues)
    
    duration = time.monotonic() - t0
    
    return {
        "url": url,
        "beacon_count": len(beacon_issues),
        "lh_count": len(lh_issues),
        "merged_count": len(merged_issues),
        "lh_failed": lh_failed,
        "upgraded": telemetry.get("severity_upgraded_count", 0),
        "new": telemetry.get("new_supplementary_count", 0) + telemetry.get("new_additional_insight_count", 0),
        "duration": duration
    }

async def run_all():
    print("Starting integration benchmarking across 10 real-world sites...")
    print("This will run Chrome headlessly for each site to capture Lighthouse telemetry.")
    print("-" * 110)
    print(f"{'URL':<30} | {'BEACON':<8} | {'LH Mapped':<10} | {'Merged Total':<12} | {'New Insights':<12} | {'Upgrades':<8} | {'Time':<6}")
    print("-" * 110)
    
    # Run sequentially so we don't completely saturate the host server
    # We'll batch them in pairs of 2 using a semaphore
    sem = asyncio.Semaphore(2)
    
    async def bounded_analyze(url):
        async with sem:
            return await analyze_site(url)
            
    tasks = [asyncio.create_task(bounded_analyze(url)) for url in SITES]
    results = await asyncio.gather(*tasks)
    
    for r in results:
        url_label = r["url"].replace("https://", "")[:28]
        if r["lh_failed"]:
            lh_str = "ERR"
            new_str = "ERR"
            upg_str = "ERR"
        else:
            lh_str = str(r['lh_count'])
            new_str = f"+{r['new']}"
            upg_str = str(r['upgraded'])
            
        print(f"{url_label:<30} | {r['beacon_count']:<8} | {lh_str:<10} | {r['merged_count']:<12} | {new_str:<12} | {upg_str:<8} | {r['duration']:.1f}s")
        
    print("-" * 110)

if __name__ == "__main__":
    asyncio.run(run_all())
