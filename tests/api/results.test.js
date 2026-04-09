const request = require("supertest");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildApi({ engineDelayMs = 120 } = {}) {
  jest.resetModules();

  process.env.NODE_ENV = "test";
  process.env.AUDIT_TIMEOUT_MS = "1000";
  process.env.RATE_LIMIT_MAX = "100";
  process.env.RATE_LIMIT_WINDOW_MS = "60000";

  const jobManager = require("../../jobs/jobManager");
  jobManager.clearJobs();
  jobManager.setAcceptingJobs(true);

  const auditService = require("../../api/services/auditService");
  auditService.__setEngineExecutor(
    () =>
      new Promise((resolve) => {
        setTimeout(() => {
          resolve({
            score: 79,
            issues: [{ rule_id: "missing-label", severity: "serious", suggested_fix: "Add label" }],
            priority_ranking: [{ rule_id: "missing-label", score: 0.9 }],
            pages_audited: 3,
            degraded_mode: false,
          });
        }, engineDelayMs);
      }),
  );

  const { createApp } = require("../../server");
  return { app: createApp() };
}

describe("Results API", () => {
  test("GET /results/:job_id returns 409 while audit is not complete", async () => {
    const { app } = buildApi({ engineDelayMs: 200 });

    const created = await request(app)
      .post("/audit")
      .send({ url: "https://example.com", mode: "balanced" });

    const response = await request(app).get(`/results/${created.body.data.job_id}`);

    expect(response.status).toBe(409);
    expect(response.body.success).toBe(false);
    expect(response.body.error.code).toBe("RESULT_NOT_READY");
    expect(["queued", "running", "timeout", "failed"]).toContain(response.body.data.status);
  });

  test("GET /results/:job_id returns normalized result after completion", async () => {
    const { app } = buildApi({ engineDelayMs: 80 });

    const created = await request(app)
      .post("/audit")
      .send({ url: "https://example.com", mode: "deep" });

    await sleep(130);

    const response = await request(app).get(`/results/${created.body.data.job_id}`);

    expect(response.status).toBe(200);
    expect(response.body.success).toBe(true);
    expect(response.body.data.job_id).toBe(created.body.data.job_id);
    expect(response.body.data.url).toBe("https://example.com");
    expect(response.body.data.mode).toBe("deep");
    expect(typeof response.body.data.score).toBe("number");
    expect(typeof response.body.data.risk_score).toBe("number");
    expect(response.body.data.grade).toBeTruthy();
    expect(Array.isArray(response.body.data.issues)).toBe(true);
    expect(Array.isArray(response.body.data.priorities)).toBe(true);
    expect(Array.isArray(response.body.data.fixes)).toBe(true);
  });

  test("GET /results/nonexistent-id returns 404", async () => {
    const { app } = buildApi();

    const response = await request(app).get("/results/nope");

    expect(response.status).toBe(404);
    expect(response.body.success).toBe(false);
    expect(response.body.error.code).toBe("JOB_NOT_FOUND");
  });
});
