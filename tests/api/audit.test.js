const request = require("supertest");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildApi({ timeoutMs = 1000, engineExecutor } = {}) {
  jest.resetModules();

  process.env.NODE_ENV = "test";
  process.env.AUDIT_TIMEOUT_MS = String(timeoutMs);
  process.env.RATE_LIMIT_MAX = "100";
  process.env.RATE_LIMIT_WINDOW_MS = "60000";

  const jobManager = require("../../jobs/jobManager");
  jobManager.clearJobs();
  jobManager.setAcceptingJobs(true);

  const auditService = require("../../api/services/auditService");
  auditService.__setEngineExecutor(
    engineExecutor ||
      (() =>
        new Promise((resolve) => {
          setTimeout(() => {
            resolve({ score: 82, issues: [], pages_audited: 1, priority_ranking: [] });
          }, 80);
        })),
  );

  const { createApp } = require("../../server");

  return {
    app: createApp(),
    jobManager,
    auditService,
  };
}

describe("Audit API", () => {
  test("POST /audit returns 202 with job_id", async () => {
    const { app } = buildApi();

    const response = await request(app)
      .post("/audit")
      .send({ url: "https://example.com/", mode: "BaLaNcEd" });

    expect(response.status).toBe(202);
    expect(response.body.success).toBe(true);
    expect(response.body.data.job_id).toBeTruthy();
    expect(response.body.data.status).toBe("queued");
    expect(response.body.data.url).toBe("https://example.com");
    expect(response.body.data.mode).toBe("balanced");
  });

  test("GET /audit/:job_id returns queued immediately", async () => {
    const { app } = buildApi({
      engineExecutor: () =>
        new Promise((resolve) => {
          setTimeout(() => resolve({ score: 90, issues: [] }), 200);
        }),
    });

    const created = await request(app)
      .post("/audit")
      .send({ url: "https://example.com", mode: "fast" });

    const polled = await request(app).get(`/audit/${created.body.data.job_id}`);

    expect(polled.status).toBe(200);
    expect(polled.body.success).toBe(true);
    expect(["queued", "running"]).toContain(polled.body.data.status);
  });

  test("job status transitions to running then completed", async () => {
    const { app } = buildApi({
      engineExecutor: () =>
        new Promise((resolve) => {
          setTimeout(() => resolve({ score: 76, issues: [] }), 180);
        }),
    });

    const created = await request(app)
      .post("/audit")
      .send({ url: "https://example.com", mode: "deep" });

    const jobId = created.body.data.job_id;
    const observedStates = new Set();

    for (let attempt = 0; attempt < 10; attempt += 1) {
      const poll = await request(app).get(`/audit/${jobId}`);
      observedStates.add(poll.body.data.status);
      if (poll.body.data.status === "completed") {
        break;
      }
      await sleep(40);
    }

    expect(observedStates.has("running") || observedStates.has("queued")).toBe(true);
    expect(observedStates.has("completed")).toBe(true);
  });

  test("GET /audit/nonexistent-id returns 404", async () => {
    const { app } = buildApi();

    const response = await request(app).get("/audit/does-not-exist");

    expect(response.status).toBe(404);
    expect(response.body.success).toBe(false);
    expect(response.body.error.code).toBe("JOB_NOT_FOUND");
  });

  test("engine failure marks job as failed while status endpoint remains stable", async () => {
    const { app } = buildApi({
      engineExecutor: async () => {
        throw new Error("simulated engine failure");
      },
    });

    const created = await request(app)
      .post("/audit")
      .send({ url: "https://example.com", mode: "fast" });

    await sleep(40);

    const poll = await request(app).get(`/audit/${created.body.data.job_id}`);
    expect(poll.status).toBe(200);
    expect(poll.body.data.status).toBe("failed");
  });

  test("timeout marks job as timeout while API remains stable", async () => {
    const { app } = buildApi({
      timeoutMs: 40,
      engineExecutor: () =>
        new Promise((resolve) => {
          setTimeout(() => resolve({ score: 90, issues: [] }), 200);
        }),
    });

    const created = await request(app)
      .post("/audit")
      .send({ url: "https://example.com", mode: "fast" });

    await sleep(90);

    const poll = await request(app).get(`/audit/${created.body.data.job_id}`);
    expect(poll.status).toBe(200);
    expect(poll.body.data.status).toBe("timeout");
  });
});
