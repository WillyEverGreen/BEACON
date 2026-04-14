import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://act-rules.github.io/testcases/e086e5/3b4e297ca20e30ab0d1bbf68edd6218a3263ca5d.html', wait_until="domcontentloaded")
        
        has_head = await page.evaluate("!!document.head")
        has_body = await page.evaluate("!!document.body")
        print(f"Has head: {has_head}")
        print(f"Has body: {has_body}")
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
