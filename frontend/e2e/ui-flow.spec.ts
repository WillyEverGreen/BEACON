import { expect, test, type Route } from "@playwright/test";

type Project = {
  id: string;
  name: string;
  url: string;
  created_at: string;
};

type ScanRecord = {
  id: string;
  project_id: string;
  status: "scanning" | "completed";
  url: string;
  scan_mode: string;
  score: number | null;
  total_issues: number;
  issue_types_count: number;
  failing_elements_count: number;
  critical_issues: number;
  serious_issues: number;
  moderate_issues: number;
  minor_issues: number;
  summary: string;
  ai_analysis: string;
  issues: Array<{ severity: string; description: string; issue_id: string }>;
  priority_ranking: Array<{ rule_family: string; severity: string; frequency: number }>;
  trust: {
    confidence_avg: number;
    suppression_rate: number;
    data_quality: string;
    audit_completeness: string;
    low_trust_rules_present: string[];
    calibration_warnings: string[];
    score_integrity: { caps_applied: unknown[] };
    engines_coverage: {
      static: boolean;
      browser: boolean;
      axe: boolean;
      heuristic: boolean;
    };
  };
  engines_used: string[];
  scan_time_seconds: number;
  pages_scanned: number;
  pages_discovered: number;
  enrichment_status: "pending" | "completed";
  created_at: string;
  completed_at: string | null;
};

async function fulfillJson(route: Route, status: number, body: unknown): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function normalizePath(pathname: string): string {
  if (pathname.length > 1 && pathname.endsWith("/")) {
    return pathname.slice(0, -1);
  }
  return pathname;
}

test("dashboard flow stays in-sync without manual reload", async ({ page }) => {
  const projects = new Map<string, Project>();
  const scansByProject = new Map<string, ScanRecord[]>();
  const progressPolls = new Map<string, number>();
  const enrichmentFetches = new Map<string, number>();
  let projectCounter = 1;
  let scanCounter = 1;

  const buildProjectSummary = (project: Project) => {
    const scans = scansByProject.get(project.id) || [];
    const latestCompleted = scans.find((scan) => scan.status === "completed") || null;

    return {
      id: project.id,
      name: project.name,
      url: project.url,
      latest_score: latestCompleted?.score ?? null,
      total_issues: latestCompleted?.total_issues ?? 0,
      last_scan_at: latestCompleted?.completed_at ?? null,
      created_at: project.created_at,
    };
  };

  page.on("dialog", async (dialog) => {
    await dialog.accept();
  });

  await page.route("**/api/beacon/config*", async (route) => {
    await fulfillJson(route, 200, {
      aiEnabled: true,
      streamEnabled: false,
      apiVersion: "v1",
    });
  });

  await page.route("**/api/beacon/v1/**", async (route) => {
    const request = route.request();
    const method = request.method().toUpperCase();
    const url = new URL(request.url());
    const path = normalizePath(url.pathname);

    if (path === "/api/beacon/v1/projects" && method === "GET") {
      const list = Array.from(projects.values())
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .map((project) => buildProjectSummary(project));
      await fulfillJson(route, 200, list);
      return;
    }

    if (path === "/api/beacon/v1/projects" && method === "POST") {
      const payload = request.postDataJSON() as { name: string; url: string };
      const now = new Date().toISOString();
      const nextProject: Project = {
        id: `p-${projectCounter++}`,
        name: payload.name,
        url: payload.url,
        created_at: now,
      };
      projects.set(nextProject.id, nextProject);
      scansByProject.set(nextProject.id, []);

      await fulfillJson(route, 200, buildProjectSummary(nextProject));
      return;
    }

    if (path.startsWith("/api/beacon/v1/projects/") && method === "GET") {
      const projectId = path.split("/").at(-1) || "";
      const project = projects.get(projectId);
      if (!project) {
        await fulfillJson(route, 404, { message: "Project not found" });
        return;
      }

      await fulfillJson(route, 200, buildProjectSummary(project));
      return;
    }

    if (path.startsWith("/api/beacon/v1/projects/") && method === "DELETE") {
      const projectId = path.split("/").at(-1) || "";
      projects.delete(projectId);
      scansByProject.delete(projectId);
      await fulfillJson(route, 200, { success: true });
      return;
    }

    if (path === "/api/beacon/v1/scans" && method === "POST") {
      const payload = request.postDataJSON() as { project_id: string; scan_mode?: string };
      const project = projects.get(payload.project_id);
      if (!project) {
        await fulfillJson(route, 404, { message: "Project not found" });
        return;
      }

      const now = new Date().toISOString();
      const scan: ScanRecord = {
        id: `s-${scanCounter++}`,
        project_id: payload.project_id,
        status: "scanning",
        url: project.url,
        scan_mode: payload.scan_mode || "fast",
        score: null,
        total_issues: 0,
        issue_types_count: 0,
        failing_elements_count: 0,
        critical_issues: 0,
        serious_issues: 0,
        moderate_issues: 0,
        minor_issues: 0,
        summary: "Scan in progress",
        ai_analysis: "AI engine is generating insights...",
        issues: [],
        priority_ranking: [],
        trust: {
          confidence_avg: 0.7,
          suppression_rate: 0,
          data_quality: "medium",
          audit_completeness: "full",
          low_trust_rules_present: [],
          calibration_warnings: [],
          score_integrity: { caps_applied: [] },
          engines_coverage: {
            static: true,
            browser: false,
            axe: false,
            heuristic: true,
          },
        },
        engines_used: ["static", "heuristic"],
        scan_time_seconds: 0,
        pages_scanned: 1,
        pages_discovered: 1,
        enrichment_status: "pending",
        created_at: now,
        completed_at: null,
      };

      const scans = scansByProject.get(payload.project_id) || [];
      scansByProject.set(payload.project_id, [scan, ...scans]);
      progressPolls.set(scan.id, 0);
      enrichmentFetches.set(scan.id, 0);

      await fulfillJson(route, 200, {
        id: scan.id,
        status: "scanning",
      });
      return;
    }

    if (path.startsWith("/api/beacon/v1/scans/") && method === "GET") {
      const segments = path.split("/").filter(Boolean);
      const projectId = segments[4] || "";
      const scanId = segments[5] || null;
      const isProgressRequest = segments[6] === "progress";

      if (!scanId) {
        const scans = scansByProject.get(projectId) || [];
        const hydratedScans = scans.map((scan) => {
          if (scan.status === "completed" && scan.enrichment_status === "pending") {
            const tries = (enrichmentFetches.get(scan.id) || 0) + 1;
            enrichmentFetches.set(scan.id, tries);

            if (tries >= 2) {
              return {
                ...scan,
                enrichment_status: "completed" as const,
                ai_analysis: "AI summary generated for this run.",
              };
            }
          }
          return scan;
        });

        scansByProject.set(projectId, hydratedScans);
        await fulfillJson(route, 200, hydratedScans);
        return;
      }

      if (isProgressRequest) {
        const scans = scansByProject.get(projectId) || [];
        const target = scans.find((scan) => scan.id === scanId);
        if (!target) {
          await fulfillJson(route, 404, { message: "Scan not found" });
          return;
        }

        const polls = (progressPolls.get(scanId) || 0) + 1;
        progressPolls.set(scanId, polls);

        if (polls >= 2) {
          target.status = "completed";
          target.score = 95;
          target.total_issues = 6;
          target.issue_types_count = 6;
          target.failing_elements_count = 6;
          target.critical_issues = 0;
          target.serious_issues = 1;
          target.moderate_issues = 2;
          target.minor_issues = 3;
          target.summary = "Scan successful.";
          target.ai_analysis = "AI engine is generating insights...";
          target.scan_time_seconds = 0.6;
          target.issues = [
            { issue_id: "i-1", severity: "serious", description: "Image missing alt text" },
            { issue_id: "i-2", severity: "moderate", description: "Low color contrast" },
            { issue_id: "i-3", severity: "moderate", description: "Form input missing label" },
            { issue_id: "i-4", severity: "minor", description: "Heading order skipped" },
            { issue_id: "i-5", severity: "minor", description: "Link text is non-descriptive" },
            { issue_id: "i-6", severity: "minor", description: "Missing focus style" },
          ];
          target.priority_ranking = [
            { rule_family: "Image alternative text", severity: "serious", frequency: 2 },
          ];
          target.completed_at = new Date().toISOString();
        }

        await fulfillJson(route, 200, {
          status: target.status,
          progress: target.status === "completed" ? 100 : 45,
        });
        return;
      }

      const scans = scansByProject.get(projectId) || [];
      const target = scans.find((scan) => scan.id === scanId);
      if (!target) {
        await fulfillJson(route, 404, { message: "Scan not found" });
        return;
      }
      await fulfillJson(route, 200, target);
      return;
    }

    await fulfillJson(route, 404, { message: `Unhandled mock route for ${path}` });
  });

  await page.goto("/dashboard");
  await expect(page.getByRole("button", { name: "New Project" })).toBeVisible({
    timeout: 15000,
  });
  await expect(page.getByRole("heading", { name: "All Projects" })).toBeVisible({
    timeout: 15000,
  });
  await expect(page.getByText("No projects yet")).toBeVisible();

  await page.getByRole("button", { name: "New Project" }).click();
  await page.getByPlaceholder("Product Landing Page").fill("Playwright Flow Project");
  await page.getByPlaceholder("https://example.com").fill("https://example.com");
  await page.getByRole("button", { name: "Launch Project" }).click();

  await expect(page.getByRole("status")).toContainText("created", { timeout: 8000 });
  const projectCard = page.getByRole("link", { name: /Playwright Flow Project/i });
  await expect(projectCard).toBeVisible();

  await projectCard.click();
  await expect(page).toHaveURL(/\/dashboard\/p-1$/);
  await expect(page.getByRole("heading", { name: "No scan results" })).toBeVisible();

  await page.getByRole("button", { name: "Initiate Scan" }).click();
  await expect(page.getByRole("heading", { name: "Scanning in progress" })).toBeVisible();
  await expect(page.getByText("Scan successful! Results synchronized.")).toBeVisible({
    timeout: 20000,
  });

  await expect(page.getByText("Refreshing insights...")).toBeVisible();
  await expect(page.getByText("AI summary generated for this run.")).toBeVisible({
    timeout: 20000,
  });

  await page.getByRole("link", { name: "Back to Projects" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  const updatedProjectCard = page.getByRole("link", { name: /Playwright Flow Project/i });
  await expect(updatedProjectCard).toContainText("95/100");
  await expect(updatedProjectCard).toContainText("6 issues");

  await updatedProjectCard
    .getByRole("button", { name: "Delete project permanently" })
    .click();

  await expect(page.getByRole("status")).toContainText("Deleted", {
    timeout: 10000,
  });
  await expect(page.getByRole("link", { name: /Playwright Flow Project/i })).toHaveCount(0);
});
