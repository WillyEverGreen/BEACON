const request = require("supertest");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildApi() {
  jest.resetModules();

  process.env.NODE_ENV = "test";
  process.env.AUDIT_TIMEOUT_MS = "3000";
  process.env.RATE_LIMIT_MAX = "1000";
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
            score: 84,
            issues: [],
            pages_audited: 1,
            priority_ranking: [],
          });
        }, 120);
      }),
  );

  const { createApp } = require("../../server");

  return {
    app: createApp(),
    auditService,
  };
}

describe("Concurrent Audit Requests", () => {
  test("handles 10 concurrent POST /audit requests and completes all jobs", async () => {
    const { app, auditService } = buildApi();

    const createRequests = Array.from({ length: 10 }, (_, index) =>
      request(app)
        .post("/audit")
        .send({ url: `https://example.com/page-${index}`, mode: "balanced" }),
    );

    const createResponses = await Promise.all(createRequests);

    createResponses.forEach((response) => {
      expect(response.status).toBe(202);
      expect(response.body.success).toBe(true);
      expect(response.body.data.job_id).toBeTruthy();
      expect(response.body.data.status).toBe("queued");
    });

    const jobIds = createResponses.map((response) => response.body.data.job_id);
    expect(new Set(jobIds).size).toBe(10);

    let finalStatuses = [];

    for (let attempt = 0; attempt < 40; attempt += 1) {
      const polls = await Promise.all(jobIds.map((jobId) => request(app).get(`/audit/${jobId}`)));
      finalStatuses = polls.map((poll) => poll.body?.data?.status);

      if (finalStatuses.every((status) => status === "completed")) {
        break;
      }

      await sleep(50);
    }

    expect(finalStatuses).toHaveLength(10);
    expect(finalStatuses.every((status) => status === "completed")).toBe(true);

    const health = await request(app).get("/health");
    expect(health.status).toBe(200);
    expect(health.body.success).toBe(true);
    expect(health.body.data.jobs.completed).toBe(10);
    expect(health.body.data.jobs.running).toBe(0);
    expect(health.body.data.jobs.queued).toBe(0);

    auditService.__resetEngineExecutor();
  });
});