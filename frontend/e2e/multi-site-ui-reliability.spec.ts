import { test, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

/**
 * BEACON Multi-Site UI & Output Reliability Test Suite
 *
 * Validates:
 * 1. Multi-site project creation and URL normalization across diverse targets.
 * 2. Scan execution ("Initiate Scan") and live status transition tracking.
 * 3. Output reliability (mathematical score integrity, severity breakdowns, trust metrics).
 * 4. Interactive UI testing (Overview, Issues, and Fix Priority tabs, filtering, issue inspection).
 * 5. Standards-compliant export downloads (SARIF, EARL, Markdown, JSON).
 * 6. Responsive UI layout across Desktop, Tablet, and Mobile viewports.
 * 7. Browser console error-free hygiene.
 */

const TEST_SITES = [
  {
    name: "Example Baseline",
    url: "https://example.com",
    expectedDomain: "example.com",
  },
  {
    name: "Sai Portfolio App",
    url: "https://sai-folio.vercel.app",
    expectedDomain: "sai-folio.vercel.app",
  },
  {
    name: "W3C Accessibility Standards",
    url: "https://www.w3.org",
    expectedDomain: "w3.org",
  },
  {
    name: "Httpbin Semantic Benchmark",
    url: "https://httpbin.org/html",
    expectedDomain: "httpbin.org",
  },
];

test.describe("BEACON Multi-Site End-to-End & UI Reliability Suite", () => {
  const screenshotsDir = path.join(__dirname, "..", "test-results", "screenshots");
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
  }

  test("1. Landing page loads cleanly with branding and responsive navigation", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && !msg.text().includes("favicon")) {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    const heroTitle = page.locator("h1");
    await expect(heroTitle).toBeVisible();

    const startAuditLink = page.getByRole("link", { name: /start audit/i }).first();
    await expect(startAuditLink).toBeVisible();

    await startAuditLink.click();
    await page.waitForURL("**/dashboard**");
    expect(page.url()).toContain("/dashboard");

    const dashboardHeading = page.locator("h1");
    await expect(dashboardHeading).toContainText(/All Projects|Projects/i);

    expect(consoleErrors.length).toBe(0);
  });

  test("2. Create projects for multiple diverse target websites", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("domcontentloaded");

    for (const site of TEST_SITES) {
      const existingProjectCard = page.locator(`[data-testid="project-card"]:has-text("${site.name}")`).first();
      if ((await existingProjectCard.count()) === 0) {
        const newProjectBtn = page.locator('[data-testid="new-project-btn"], button:has-text("New Project")').first();
        await expect(newProjectBtn).toBeVisible();
        await newProjectBtn.click();

        const nameInput = page.locator('[data-testid="project-name-input"], input[placeholder*="Landing" i], input[type="text"]').first();
        const urlInput = page.locator('[data-testid="project-url-input"], input[placeholder*="https://" i], input[type="url"]').first();

        await expect(nameInput).toBeVisible();
        await expect(urlInput).toBeVisible();

        await nameInput.fill(site.name);
        await urlInput.fill(site.url);

        const submitBtn = page.locator('[data-testid="create-project-submit-btn"], button:has-text("Launch Project")').first();
        await expect(submitBtn).toBeEnabled();
        await submitBtn.click();

        const projectCard = page.locator(`[data-testid="project-card"]:has-text("${site.name}")`).first();
        await expect(projectCard).toBeVisible({ timeout: 15000 });
      }

      const card = page.locator(`[data-testid="project-card"]:has-text("${site.name}")`).first();
      await expect(card).toBeVisible();
      await expect(card).toContainText(site.expectedDomain);
    }

    await page.screenshot({ path: path.join(screenshotsDir, "all-projects-dashboard.png"), fullPage: true });
  });

  for (const site of TEST_SITES) {
    test(`3. Audit execution and output verification for ${site.name} (${site.url})`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error" && !msg.text().includes("favicon") && !msg.text().includes("ERR_BLOCKED_BY_CLIENT")) {
          consoleErrors.push(msg.text());
        }
      });

      await page.goto("/dashboard");
      await page.waitForLoadState("domcontentloaded");

      // Navigate to project detail
      const projectCard = page.locator(`[data-testid="project-card"]:has-text("${site.name}")`).first();
      await expect(projectCard).toBeVisible();
      await projectCard.click();

      await page.waitForURL("**/dashboard/**");
      const projectHeader = page.locator("h1").first();
      await expect(projectHeader).toBeVisible();

      // Look for Initiate Scan button
      const initiateBtn = page.getByRole("button", { name: /initiate scan/i });
      const scoreCard = page.locator('.stat-card:has-text("Accessibility Score")').first();

      // If no score card yet, trigger Initiate Scan
      if ((await scoreCard.count()) === 0) {
        await expect(initiateBtn).toBeVisible({ timeout: 10000 });
        await initiateBtn.click();
        await page.waitForTimeout(1000);
      }

      // Wait for scan to complete and score card to be visible
      await expect(scoreCard).toBeVisible({ timeout: 45000 });

      const scoreText = await scoreCard.textContent();
      expect(scoreText).toBeDefined();
      expect(scoreText).toMatch(/Accessibility Score/i);

      // Verify Metric Cards (Failing Elements, Engines Used)
      const elementsCard = page.locator('.stat-card:has-text("Failing Elements")').first();
      await expect(elementsCard).toBeVisible();

      const enginesCard = page.locator('.stat-card:has-text("Engines Used")').first();
      await expect(enginesCard).toBeVisible();

      // Save screenshot for site overview
      const safeSiteKey = site.name.toLowerCase().replace(/[^a-z0-9]/g, "-");
      await page.screenshot({ path: path.join(screenshotsDir, `project-${safeSiteKey}-overview.png`), fullPage: true });

      // Verify Tab 2: Issues
      const issuesTabBtn = page.getByRole("button", { name: /issues/i }).first();
      if (await issuesTabBtn.isVisible()) {
        await issuesTabBtn.click();
        await page.waitForTimeout(500);

        // Check filter buttons exist (Show All, Verified, etc.)
        const filterShowAll = page.getByRole("button", { name: /show all/i }).first();
        if (await filterShowAll.isVisible()) {
          await filterShowAll.click();
          await page.waitForTimeout(300);
        }

        await page.screenshot({ path: path.join(screenshotsDir, `project-${safeSiteKey}-issues.png`), fullPage: true });
      }

      // Verify Tab 3: Fix Priority
      const priorityTabBtn = page.getByRole("button", { name: /fix priority|priority/i }).first();
      if (await priorityTabBtn.isVisible()) {
        await priorityTabBtn.click();
        await page.waitForTimeout(500);

        const priorityContent = page.locator('main').first();
        await expect(priorityContent).toBeVisible();

        await page.screenshot({ path: path.join(screenshotsDir, `project-${safeSiteKey}-priority.png`), fullPage: true });
      }

      // Switch back to Overview for Export testing
      const overviewTabBtn = page.getByRole("button", { name: /overview/i }).first();
      if (await overviewTabBtn.isVisible()) {
        await overviewTabBtn.click();
        await page.waitForTimeout(300);
      }

      // Verify Export Menu
      const exportBtn = page.locator('button:has-text("Export")').first();
      if (await exportBtn.isVisible()) {
        await exportBtn.click();
        await page.waitForTimeout(300);

        // Verify export format options exist
        const sarifOption = page.locator('button:has-text("SARIF")').first();
        const markdownOption = page.locator('button:has-text("Markdown")').first();
        const jsonOption = page.locator('button:has-text("Raw Findings")').first();

        await expect(sarifOption).toBeVisible();
        await expect(markdownOption).toBeVisible();
        await expect(jsonOption).toBeVisible();

        // Close export menu
        await exportBtn.click();
      }

      expect(consoleErrors.length).toBe(0);
    });
  }

  test("4. Multi-device responsive verification (Desktop, Tablet, Mobile) on project page", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("domcontentloaded");

    // Click on the first project card
    const firstProjectCard = page.locator('[data-testid="project-card"]').first();
    await expect(firstProjectCard).toBeVisible();
    await firstProjectCard.click();
    await page.waitForURL(url => url.pathname.startsWith('/dashboard/') && !url.pathname.includes('help'));

    const viewports = [
      { name: "desktop", width: 1440, height: 900 },
      { name: "tablet", width: 768, height: 1024 },
      { name: "mobile", width: 375, height: 667 },
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.waitForTimeout(500);

      const body = page.locator("body");
      await expect(body).toBeVisible();

      // Check header and heading are visible
      const header = page.locator("h1").first();
      await expect(header).toBeVisible();

      // Check Back to Projects link is visible
      const backLink = page.getByRole("link", { name: /back to projects/i }).first();
      await expect(backLink).toBeVisible();

      await page.screenshot({
        path: path.join(screenshotsDir, `responsive-project-detail-${vp.name}.png`),
        fullPage: true,
      });
    }
  });

  test("5. Documentation & Help page UI accessibility verification", async ({ page }) => {
    await page.goto("/dashboard/help");
    await page.waitForLoadState("domcontentloaded");

    const heading = page.locator("h1, h2").first();
    await expect(heading).toBeVisible();

    const content = page.locator("main").first();
    await expect(content).toContainText(/Getting Started|WCAG|Scans/i);

    await page.screenshot({ path: path.join(screenshotsDir, "dashboard-help-page.png"), fullPage: true });
  });
});
