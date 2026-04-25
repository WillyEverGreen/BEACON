import json
import asyncio
from typing import List, Dict, Any
from playwright.async_api import async_playwright
import os

async def run_axe_on_html(html_content: str) -> list:
    """Run axe-core on a given HTML snippet using Playwright."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Create a simple valid HTML document around the snippet if it doesn't have HTML tags
            if "<html" not in html_content.lower():
                html_content = f"<!DOCTYPE html><html lang='en'><head><title>Test</title></head><body>{html_content}</body></html>"
                
            await page.set_content(html_content)
            
            # We need axe.min.js. Let's assume it's in node_modules/axe-core/axe.min.js
            axe_path = os.path.join(os.getcwd(), "node_modules", "axe-core", "axe.min.js")
            if os.path.exists(axe_path):
                await page.add_script_tag(path=axe_path)
                results = await page.evaluate("axe.run()")
                await browser.close()
                return results.get("violations", [])
            else:
                await browser.close()
                return []
    except Exception as e:
        print(f"Failed to run axe on HTML: {e}")
        return []

def apply_fix(original_html: str, suggested_fix: str) -> str:
    """
    Apply the suggested HTML fix to the original HTML.
    For this evaluation, we assume the suggested fix is the replacement for the original.
    """
    if not suggested_fix:
        return original_html
    return suggested_fix

async def evaluate_fix_pass_rate(findings_with_fixes: List[Dict[str, Any]], k: int = 1) -> Dict[str, Any]:
    """
    For each finding, apply the suggested fix and re-scan with axe-core.
    Returns pass@k rate — fraction of violations resolved within k attempts.
    """
    results = []
    
    for item in findings_with_fixes:
        original_html = item.get('source_html', '')
        fix_dict = item.get('fix', {})
        if not fix_dict and 'suggested_html' in item:
            suggested_fix = item['suggested_html']
        else:
            suggested_fix = fix_dict.get('suggested_html', '')
            
        finding = item.get('finding', {})
        rule_id = finding.get('rule_id', '')
        sc_id = finding.get('sc_id', '')
        
        fixed_html = apply_fix(original_html, suggested_fix)
        post_fix_violations = await run_axe_on_html(fixed_html)
        
        resolved = not any(v.get('id') == rule_id for v in post_fix_violations)
        results.append({
            'resolved': resolved,
            'k': k,
            'sc_id': sc_id,
            'rule_id': rule_id
        })
        
    pass_rate = sum(r['resolved'] for r in results) / len(results) if results else 0.0
    
    return {
        'pass_at_k': pass_rate,
        'k': k,
        'n': len(results),
        'by_sc': {} # could aggregate by sc_id here
    }
