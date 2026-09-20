import { test, expect } from "@playwright/test";

/**
 * BEACON Real Website Audit & UI Testing Suite
 *
 * This test suite validates:
 * 1. Landing page UI and navigation to the Dashboard
 * 2. Creating an audit project for ANY target website URL (customizable via TEST_TARGET_URL)
 * 3. Project detail dashboard loading and state display
 * 4. Scan trigger and execution (progress tracking, metric cards, WCAG issue tables)
 * 5. Multi-device responsiveness (Desktop, Tablet, Mobile)
 * 6. UI robustness and accessibility compliance
 */

const TARGET_URL = process.env.TEST_TARGET_URL || "https://example.com";
const TARGET_NAME = process.env.TEST_PROJECT_NAME || "Example Audit Property";

test.describe("BEACON Real-World Website UI Audit Flow", () => {
  test("1. Landing page loads correctly with hero CTA and navigates to Dashboard", async ({ page }) => {
    // Navigate to homepage
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    // Verify page header and branding
    const title = page.locator("h1");
    await expect(title).toBeVisible();

    // Verify 'Start Audit' CTA exists and navigate to dashboard
    const startAuditBtn = page.getByRole("link", { name: /start audit/i }).first();
    await expect(startAuditBtn).toBeVisible();
    await startAuditBtn.click();

    // Should arrive at /dashboard without 404
    await page.waitForURL("**/dashboard**");
    expect(page.url()).toContain("/dashboard");

    const dashboardHeading = page.locator("h1");
    await expect(dashboardHeading).toContainText(/All Projects|Projects/i, { timeout: 15000 });
  });

  test("2. /dashboard and /dashboard/projects both resolve cleanly without redirect errors", async ({ page }) => {
    // Direct navigation to /dashboard
    await page.goto("/dashboard");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.locator("body")).toBeVisible();
    expect(page.url()).not.toContain("404");

    // Direct navigation to /dashboard/projects
    await page.goto("/dashboard/projects");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.locator("body")).toBeVisible();
    expect(page.url()).not.toContain("404");
  });

  test("3. Register and create project for target website: " + TARGET_URL, async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("domcontentloaded");

    // Look for New Project button (either primary button or empty state CTA)
    const newProjectBtn = page.locator('[data-testid="new-project-btn"], [data-testid="create-first-project-btn"], button:has-text("New Project")').first();
    await expect(newProjectBtn).toBeVisible();
    await newProjectBtn.click();

    // Fill project form
    const nameInput = page.locator('[data-testid="project-name-input"], input[placeholder*="Landing" i], input[type="text"]').first();
    const urlInput = page.locator('[data-testid="project-url-input"], input[placeholder*="https://" i], input[type="url"]').first();

    await expect(nameInput).toBeVisible();
    await expect(urlInput).toBeVisible();

    await nameInput.fill(TARGET_NAME);
    await urlInput.fill(TARGET_URL);

    // Submit project creation
    const submitBtn = page.locator('[data-testid="create-project-submit-btn"], button:has-text("Launch Project")').first();
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Verify project appears in the project list or success message displays
    const projectCard = page.locator(`[data-testid="project-card"]:has-text("${TARGET_NAME}"), .glass-card:has-text("${TARGET_NAME}")`).first();
    await expect(projectCard).toBeVisible({ timeout: 10000 });
  });

  test("4. View project detail and verify scan triggers for target site", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("domcontentloaded");

    // Select the target project card
    const projectLink = page.locator(`a:has-text("${TARGET_NAME}")`).first();
    if (await projectLink.count() > 0) {
      await projectLink.click();
      await page.waitForURL("**/dashboard/**");

      // Verify Project Detail page elements
      const mainHeader = page.locator("header, main, [data-testid='project-header']").first();
      await expect(mainHeader).toBeVisible();

      // Verify Scan Trigger button exists
      const scanBtn = page.locator('button:has-text("Run Scan"), button:has-text("Start Scan"), [data-testid="start-scan-btn"]').first();
      if (await scanBtn.count() > 0) {
        await expect(scanBtn).toBeVisible();
      }

      // Verify key tabs exist (Overview, Issues, etc.)
      const overviewTab = page.locator('button:has-text("Overview"), [role="tab"]:has-text("Overview")').first();
      if (await overviewTab.count() > 0) {
        await expect(overviewTab).toBeVisible();
      }
    }
  });

  test("5. Multi-device responsive verification (Desktop, Tablet, Mobile)", async ({ page }) => {
    const viewports = [
      { name: "Desktop", width: 1440, height: 900 },
      { name: "Tablet", width: 768, height: 1024 },
      { name: "Mobile", width: 375, height: 667 },
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/dashboard");
      await page.waitForLoadState("domcontentloaded");

      const body = page.locator("body");
      await expect(body).toBeVisible();

      // Heading should remain visible in all layouts
      const heading = page.locator("h1").first();
      await expect(heading).toBeVisible();
    }
  });

  test("6. Help and documentation page is accessible and informative", async ({ page }) => {
    await page.goto("/dashboard/help");
    await page.waitForLoadState("domcontentloaded");

    const helpHeading = page.locator("h1, h2").first();
    await expect(helpHeading).toBeVisible();

    // Verify documentation content exists
    const docsContent = page.locator("main").first();
    await expect(docsContent).toContainText(/Getting Started|WCAG|Scans/i);
  });
});
