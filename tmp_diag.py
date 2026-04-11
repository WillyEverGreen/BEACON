import asyncio
import re
import httpx
from app.services.static_checks import StaticChecker

CASES = {
    'ACT case 1': 'https://act-rules.github.io/testcases/5f99a7/9a417788dfd68b83820b01deb71e427f8d8edc3a.html',
    'ACT case 301': 'https://act-rules.github.io/testcases/de46e4/ca2f0f03e0dddd80cef6554814b919fac1666c02.html',
    'ACT case 351': 'https://act-rules.github.io/testcases/ebe86a/4cf15d1b1716679d654eff92f59a6b1a7f3bc344.html',
    'ACT case 401': 'https://act-rules.github.io/testcases/b49b2e/439e4f0379f4b0920aa858fadc663681ec15536b.html',
}

async def fetch(url):
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        return r.text

async def main():
    for name, url in CASES.items():
        html = await fetch(url)
        sc = StaticChecker(html, url)
        issues = sc.check_headings()
        nh = [i for i in issues if i.get('rule_id') == 'no-headings']
        print(f"\n{name}")
        if not nh:
            print('  no-headings not emitted')
            continue
        e = nh[0].get('evidence', {})
        print('  no-headings emitted')
        print('  contentful_page_without_headings=', e.get('contentful_page_without_headings'))
        print('  visible_text_length=', e.get('visible_text_length'), 'contentful_blocks=', e.get('contentful_blocks'), 'dom=', e.get('dom_element_count'))
        print('  has_head_tag=', e.get('has_head_tag'), 'interactive=', e.get('interactive_element_count'), 'descendant_lang=', e.get('descendant_lang_count'), 'raw_aria_heading=', e.get('raw_aria_heading_count'))

asyncio.run(main())
