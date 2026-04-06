import asyncio
import sys
import json
sys.path.insert(0, 'd:/HACKATHON/DJ HACK')

from app.services.audit_runner import run_audit

async def test_deep_with_playwright():
    sites = [
        ('https://www.google.com/', 'Google'),
        ('https://github.com/', 'GitHub'),  
        ('https://www.bbc.com/', 'BBC'),
        ('https://www.amazon.com/', 'Amazon'),
        ('https://news.ycombinator.com/', 'Hacker News'),
    ]
    
    results = []
    for url, name in sites:
        print(f'\n{"="*60}')
        print(f'Testing {name} with DEEP SCAN')
        print('='*60)
        
        try:
            result = await run_audit(
                url=url, 
                scan_mode='deep',
                precision_profile='balanced'
            )
            
            print(f'✓ Score: {result.get("score", 0)}/100')
            print(f'  Issues: {result.get("total_issues", 0)}')
            print(f'  Engines: {", ".join(result.get("engines_used", []))}')
            print(f'  SPA: {result.get("spa_framework", "N/A")}')
            print(f'  Degraded: {result.get("degraded_mode", False)}')
            
            results.append({
                'name': name,
                'url': url,
                'score': result.get('score'),
                'issues': result.get('total_issues'),
                'engines': result.get('engines_used'),
                'spa_framework': result.get('spa_framework'),
                'is_spa': result.get('is_spa'),
                'degraded': result.get('degraded_mode')
            })
            
        except Exception as e:
            print(f'✗ ERROR: {e}')
            results.append({'name': name, 'url': url, 'error': str(e)})
    
    # Save results
    import os
    os.makedirs('tests', exist_ok=True)
    with open('tests/deep_scan_with_playwright.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Summary
    print(f'\n{"="*60}')
    print('SUMMARY - Deep Scan with Playwright')
    print('='*60)
    
    successful = [r for r in results if 'error' not in r]
    degraded = [r for r in successful if r.get('degraded')]
    spa_detected = [r for r in successful if r.get('is_spa')]
    
    print(f'Successful: {len(successful)}/5')
    print(f'Degraded: {len(degraded)}')
    print(f'SPAs detected: {len(spa_detected)}')
    
    if spa_detected:
        print('\nSPA Frameworks:')
        for r in spa_detected:
            print(f'  - {r["name"]}: {r["spa_framework"]}')
    
    if successful:
        engines_used = set()
        for r in successful:
            engines_used.update(r.get('engines', []))
        print(f'\nEngines used: {", ".join(sorted(engines_used))}')
    
    return results

if __name__ == '__main__':
    asyncio.run(test_deep_with_playwright())
