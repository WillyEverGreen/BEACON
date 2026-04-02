import asyncio
import json
import os
from app.services.audit_runner import run_audit

async def main():
    html_content = """
    <html>
        <head><title>Test Visibility</title></head>
        <body>
            <div id='hidden' style='display:none'>
                <img src='bad1.jpg' alt='' class='issue1' />
            </div>
            <img src='bad2.jpg' alt='' class='issue2' />
            <button></button>
            <nav><a href="#main">skip</a><a href="#">1</a><a href="#">2</a><a href="#">3</a><a href="#">4</a></nav>
        </body>
    </html>
    """
    test_file = os.path.abspath("test_visibility.html")
    with open(test_file, "w") as f:
        f.write(html_content)
    
    url = f"file:///{test_file.replace(chr(92), '/')}"
    
    print(f"Auditing {url} ...")
    res = await run_audit(url, scan_mode='deep', precision_profile='balanced')
    print("\n=== ISSUES FOUND ===")
    for i in res['issues']:
        print(f"Rule: {i['rule_id']} | Element: {i['element']} | Conf: {i['confidence']}")
    print(f"\nVisibility issues filtered: {res.get('quality_gates', {}).get('visibility_filtered', 0)}")
    
if __name__ == "__main__":
    asyncio.run(main())
