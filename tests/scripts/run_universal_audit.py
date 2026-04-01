import asyncio
import json
import logging
import argparse
from urllib.parse import urlparse
from pathlib import Path
from crawl4ai import AsyncWebCrawler
from app.services.audit_runner import run_audit

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def scan_url(
    start_url: str,
    max_depth: int = 1,
    max_pages: int = 5,
    precision_profile: str = "balanced",
):
    """
    Crawls the given URL up to max_depth and runs the BEACON Mastery Audit
    on the discovered pages.
    """
    base_domain = urlparse(start_url).netloc
    visited = set()
    queue = [(start_url, 0)]
    pages_to_audit = []

    logger.info(f"🚀 Starting Universal Fast Crawl on: {start_url} (Depth: {max_depth}, Max Pages: {max_pages})")
    
    async with AsyncWebCrawler() as crawler:
        while queue and len(pages_to_audit) < max_pages:
            url, depth = queue.pop(0)
            
            if url in visited or depth > max_depth:
                continue
                
            domain = urlparse(url).netloc
            if not domain.endswith(base_domain):
                continue
                
            visited.add(url)
            logger.info(f"🕷️ Crawling: {url} (Depth {depth})")
            
            try:
                result = await crawler.arun(url=url)
                if not result.success:
                    continue
                    
                pages_to_audit.append(url)
                
                # Extract internal links for deeper crawling
                links = result.links.get("internal", [])
                for link in links:
                    href = link.get("href", "")
                    if href and href not in visited:
                        queue.append((href, depth + 1))
            except Exception as e:
                logger.warning(f"Failed to crawl {url}: {e}")

    logger.info(f"✅ Crawl complete. Found {len(pages_to_audit)} pages to audit.")
    
    # Run the Audit Engine on discovered pages
    all_results = {}
    for i, page_url in enumerate(pages_to_audit):
        logger.info(f"\n[{i+1}/{len(pages_to_audit)}] 🛡️ Running Mastery Audit on: {page_url}")
        try:
            # Using deep mode for full detection and RAG enrichment
            audit_result = await run_audit(
                page_url,
                scan_mode="deep",
                precision_profile=precision_profile,
            )
            all_results[page_url] = audit_result
            
            logger.info(f"Found {audit_result.get('total_issues', 0)} issues on {page_url} (Score: {audit_result.get('score', 0)}/100)")
        except Exception as e:
            logger.error(f"Audit failed for {page_url}: {e}")

    # Save aggregate results
    out_file = "universal_audit_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
        
    logger.info(f"\n🎉 Universal Audit Complete! Results saved to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BEACON Universal Fast Crawler & Auditor")
    parser.add_argument("url", help="The target URL to scan")
    parser.add_argument("--depth", type=int, default=1, help="Maximum crawl depth (default: 1)")
    parser.add_argument("--max-pages", "-m", type=int, default=3, help="Maximum number of pages to audit (default: 3)")
    parser.add_argument(
        "--profile",
        choices=["balanced", "high_precision"],
        default="balanced",
        help="Precision profile: balanced (higher recall) or high_precision (lower false positives)",
    )
    
    args = parser.parse_args()
    asyncio.run(scan_url(args.url, args.depth, args.max_pages, args.profile))
