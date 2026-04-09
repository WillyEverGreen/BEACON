const express = require("express");
const request = require("supertest");

function buildApi() {
  jest.resetModules();
  process.env.NODE_ENV = "test";
  process.env.RATE_LIMIT_MAX = "100";
  process.env.RATE_LIMIT_WINDOW_MS = "60000";

  const jobManager = require("../../jobs/jobManager");
  jobManager.clearJobs();
  jobManager.setAcceptingJobs(true);

  const auditService = require("../../api/services/auditService");
  auditService.__setEngineExecutor(async () => ({ score: 90, issues: [] }));

  const { createApp } = require("../../server");
  return { app: createApp() };
}

describe("Health API", () => {
  test("GET /health returns uptime and job counters", async () => {
    const { app } = buildApi();

    const response = await request(app).get("/health");

    expect(response.status).toBe(200);
    expect(response.body.success).toBe(true);
    expect(response.body.data.status).toBe("ok");
    expect(typeof response.body.data.uptime_s).toBe("number");
    expect(response.body.data.jobs).toHaveProperty("queued");
    expect(response.body.data.jobs).toHaveProperty("running");
    expect(response.body.data.jobs).toHaveProperty("completed");
    expect(response.body.data.jobs).toHaveProperty("failed");
    expect(response.body.data.timestamp).toBeTruthy();
  });

  test("unhandled middleware error returns 500 with standard envelope", async () => {
    const errorHandler = require("../../api/middlewares/errorHandler");

    const app = express();
    app.get("/boom", (req, res, next) => {
      next(new Error("simulated middleware failure"));
    });
    app.use(errorHandler);

    const response = await request(app).get("/boom");

    expect(response.status).toBe(500);
    expect(response.body.success).toBe(false);
    expect(response.body.data).toBeNull();
    expect(response.body.error.code).toBe("INTERNAL_SERVER_ERROR");
  });
});
