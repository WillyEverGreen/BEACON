"""
Script to capture high-resolution Retina product screenshots of the BEACON live platform using Playwright.
"""
import os
import time
from playwright.sync_api import sync_playwright

OUTPUT_DIR = os.path.abspath(r"d:\FullStack Projects\BEACON\BEACON\frontend\public\screenshots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TARGET_BASE = "https://frontend-seven-phi-64.vercel.app"

def capture():
    print(f"Starting screenshot capture against {TARGET_BASE}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 1440x900 with 2x scale factor gives razor-sharp 2880x1800 Retina captures
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            color_scheme="dark",
        )
        page = context.new_page()

        # 1. Main Dashboard Overview
        print("Navigating to /dashboard...")
        page.goto(f"{TARGET_BASE}/dashboard", wait_until="networkidle", timeout=30000)
        time.sleep(3) # allow any animations / charts to settle
        
        dashboard_path = os.path.join(OUTPUT_DIR, "dashboard-overview.png")
        page.screenshot(path=dashboard_path, full_page=False)
        print(f"Captured: {dashboard_path}")

        # 2. Try to click on an audit item or inspect issues
        # Look for buttons or cards or table rows
        try:
            # Look for project card or row
            row = page.locator("a[href*='/dashboard/'], button:has-text('View'), tr").first
            if row.is_visible():
                row.click()
                time.sleep(2)
                page.wait_for_load_state("networkidle", timeout=10000)
                time.sleep(2)
                inspector_path = os.path.join(OUTPUT_DIR, "audit-inspector.png")
                page.screenshot(path=inspector_path, full_page=False)
                print(f"Captured: {inspector_path}")
        except Exception as e:
            print(f"Notice during secondary capture: {e}")

        # If secondary didn't capture, take a focused screenshot of the dashboard's main container
        if not os.path.exists(os.path.join(OUTPUT_DIR, "audit-inspector.png")):
            inspector_path = os.path.join(OUTPUT_DIR, "audit-inspector.png")
            page.screenshot(path=inspector_path, full_page=False)

        browser.close()
        print("Screenshot capture complete!")

if __name__ == "__main__":
    capture()
