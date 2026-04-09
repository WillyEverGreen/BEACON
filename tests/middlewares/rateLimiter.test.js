const express = require("express");
const request = require("supertest");

function buildApp() {
  jest.resetModules();
  process.env.RATE_LIMIT_MAX = "5";
  process.env.RATE_LIMIT_WINDOW_MS = "1000";

  const { rateLimiter, __resetRateLimiter } = require("../../api/middlewares/rateLimiter");

  const app = express();
  app.set("trust proxy", true);
  app.use(rateLimiter);
  app.get("/ping", (req, res) => res.status(200).json({ ok: true }));

  return { app, __resetRateLimiter };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

describe("rateLimiter middleware", () => {
  test("6th request in the same window returns 429", async () => {
    const { app, __resetRateLimiter } = buildApp();

    for (let count = 0; count < 5; count += 1) {
      const ok = await request(app)
        .get("/ping")
        .set("X-Forwarded-For", "8.8.8.8");
      expect(ok.status).toBe(200);
    }

    const blocked = await request(app)
      .get("/ping")
      .set("X-Forwarded-For", "8.8.8.8");

    expect(blocked.status).toBe(429);
    expect(blocked.body.error.code).toBe("RATE_LIMIT_EXCEEDED");
    expect(blocked.body.error.retry_after_s).toBeGreaterThanOrEqual(1);

    __resetRateLimiter();
  });

  test("request succeeds after window reset", async () => {
    const { app, __resetRateLimiter } = buildApp();

    for (let count = 0; count < 6; count += 1) {
      await request(app)
        .get("/ping")
        .set("X-Forwarded-For", "9.9.9.9");
    }

    await sleep(1100);

    const afterReset = await request(app)
      .get("/ping")
      .set("X-Forwarded-For", "9.9.9.9");

    expect(afterReset.status).toBe(200);

    __resetRateLimiter();
  });
});
