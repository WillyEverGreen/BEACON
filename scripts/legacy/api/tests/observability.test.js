const request = require("supertest");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildApi({ timeoutMs = 1000, engineDelayMs = 80 } = {}) {
  jest.resetModules();

  process.env.NODE_ENV = "test";
  process.env.AUDIT_TIMEOUT_MS = String(timeoutMs);
  process.env.REQUEST_TIMEOUT_MS = "10000";
  process.env.RATE_LIMIT_MAX = "1000";
  process.env.RATE_LIMIT_WINDOW_MS = "60000";

  const { metrics } = require("../utils/metrics");
  metrics.reset();

  const jobManager = require("../../jobs/jobManager");
  jobManager.clearJobs();
  jobManager.setAcceptingJobs(true);

  const auditService = require("../services/auditService");
  auditService.__setEngineExecutor(
    () =>
      new Promise((resolve) => {
        setTimeout(() => {
          resolve({
            score: 88,
            issues: [],
            priority_ranking: [],
            pages_audited: 1,
          });
        }, engineDelayMs);
      }),
  );

  const { createApp } = require("../../server");
  return {
    app: createApp(),
    metrics,
    auditService,
    jobManager,
  };
}

describe("Phase 8 Observability", () => {
  test("logger emits structured JSON and redacts sensitive fields", () => {
    jest.resetModules();

    const logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    const { log } = require("../utils/logger");

    log("info", "request_received", {
      request_id: "req_test_1",
      job_id: "job_test_1",
      duration_ms: 9,
      token: "abc123",
      html: "<html>secret</html>",
      method: "POST",
    });

    expect(logSpy).toHaveBeenCalledTimes(1);
    const infoPayload = JSON.parse(logSpy.mock.calls[0][0]);
    expect(infoPayload).toEqual(
      expect.objectContaining({
        level: "info",
        event: "request_received",
        request_id: "req_test_1",
        job_id: "job_test_1",
        duration_ms: 9,
      }),
    );
    expect(infoPayload.meta.token).toBe("[REDACTED]");
    expect(infoPayload.meta.html).toBe("[REDACTED]");

    log("error", "internal_error", {
      request_id: "req_test_2",
      message: "boom",
    });

    expect(errorSpy).toHaveBeenCalledTimes(1);
    const errorPayload = JSON.parse(errorSpy.mock.calls[0][0]);
    expect(errorPayload.level).toBe("error");
    expect(errorPayload.event).toBe("internal_error");

    logSpy.mockRestore();
    errorSpy.mockRestore();
  });

  test("metrics counters and gauges update through audit job lifecycle", async () => {
    const { app, metrics, auditService, jobManager } = buildApi({ engineDelayMs: 100 });

    const created = await request(app)
      .post("/audit")
      .send({ url: "https://example.com/observe", mode: "balanced" });

    expect(created.status).toBe(202);
    const jobId = created.body.data.job_id;

    let finalStatus = "queued";
    for (let attempt = 0; attempt < 25; attempt += 1) {
      const poll = await request(app).get(`/audit/${jobId}`);
      finalStatus = poll.body.data.status;
      if (finalStatus === "completed") {
        break;
      }
      await sleep(40);
    }

    expect(finalStatus).toBe("completed");

    const snapshot = metrics.getSnapshot();
    expect(snapshot.counters.total_requests).toBeGreaterThanOrEqual(2);
    expect(snapshot.counters.total_audits).toBe(1);
    expect(snapshot.counters.successful_audits).toBe(1);
    expect(snapshot.gauges.active_jobs).toBe(0);
    expect(snapshot.gauges.queued_jobs).toBe(0);
    expect(snapshot.timings.execution_durations.length).toBeGreaterThan(0);
    expect(snapshot.timings.avg_execution_time).toBeGreaterThan(0);

    const storedJob = jobManager.getJob(jobId);
    expect(storedJob.request_id).toMatch(/^req_/);

    auditService.__resetEngineExecutor();
  });

  test("monitoring endpoints return valid JSON and zero-safe success rate", async () => {
    const { app } = buildApi();

    const metricsResponse = await request(app).get("/metrics");
    expect(metricsResponse.status).toBe(200);
    expect(metricsResponse.body).toEqual(
      expect.objectContaining({
        total_requests: expect.any(Number),
        total_audits: 0,
        success_rate: 0,
        avg_execution_time_ms: expect.any(Number),
        active_jobs: expect.any(Number),
        queued_jobs: expect.any(Number),
      }),
    );

    const summaryResponse = await request(app).get("/jobs/summary");
    expect(summaryResponse.status).toBe(200);
    expect(summaryResponse.body).toEqual(
      expect.objectContaining({
        queued: expect.any(Number),
        running: expect.any(Number),
        completed: expect.any(Number),
        failed: expect.any(Number),
        timeout: expect.any(Number),
      }),
    );

    const healthResponse = await request(app).get("/health");
    expect(healthResponse.status).toBe(200);
    expect(healthResponse.body).toEqual(
      expect.objectContaining({
        success: true,
        data: expect.objectContaining({
          status: "ok",
          timestamp: expect.any(String),
          active_jobs: expect.any(Number),
        }),
      }),
    );
  });

  test("metrics and logger updaters are synchronous and non-promise", () => {
    jest.resetModules();

    const logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    const { metrics } = require("../utils/metrics");
    const { log } = require("../utils/logger");

    metrics.reset();

    const a = metrics.incrementTotalRequests();
    const b = metrics.markJobQueued();
    const c = metrics.markJobStarted();
    const d = metrics.recordExecutionDuration(12);
    const e = metrics.markJobCompleted();
    const f = log("info", "request_completed", { request_id: "req_sync" });

    expect(a).toBeUndefined();
    expect(b).toBeUndefined();
    expect(c).toBeUndefined();
    expect(d).toBeUndefined();
    expect(e).toBeUndefined();
    expect(f).toBeUndefined();
    expect(logSpy).toHaveBeenCalled();

    logSpy.mockRestore();
  });

  test("metrics remain accurate under 10 parallel audits", async () => {
    const { app, metrics, auditService } = buildApi({ engineDelayMs: 120 });

    const createRequests = Array.from({ length: 10 }, (_, index) =>
      request(app)
        .post("/audit")
        .send({ url: `https://example.com/parallel-${index}`, mode: "balanced" }),
    );

    const createResponses = await Promise.all(createRequests);
    createResponses.forEach((response) => expect(response.status).toBe(202));

    const jobIds = createResponses.map((response) => response.body.data.job_id);

    for (let attempt = 0; attempt < 40; attempt += 1) {
      const polls = await Promise.all(jobIds.map((jobId) => request(app).get(`/audit/${jobId}`)));
      if (polls.every((poll) => poll.body?.data?.status === "completed")) {
        break;
      }
      await sleep(60);
    }

    const snapshot = metrics.getSnapshot();
    expect(snapshot.counters.total_audits).toBe(10);
    expect(snapshot.counters.successful_audits).toBe(10);
    expect(snapshot.gauges.active_jobs).toBe(0);
    expect(snapshot.gauges.queued_jobs).toBe(0);

    auditService.__resetEngineExecutor();
  });
});