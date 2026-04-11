const express = require("express");
const config = require("./config");
const jobManager = require("./jobs/jobManager");
const { formatError } = require("./api/controllers/responseFormatter");

const auditRoutes = require("./api/routes/audit.routes");
const resultsRoutes = require("./api/routes/results.routes");
const healthRoutes = require("./api/routes/health.routes");
const monitoringRoutes = require("./api/routes/monitoring");

const timeoutGuard = require("./api/middlewares/timeoutGuard");
const { rateLimiter } = require("./api/middlewares/rateLimiter");
const errorHandler = require("./api/middlewares/errorHandler");
const {
  observabilityMiddleware,
  registerProcessErrorHandlers,
} = require("./api/middleware/observability");
const { log } = require("./api/utils/logger");

function isMonitoringRoute(pathname) {
  return pathname === "/health" || pathname === "/metrics" || pathname === "/jobs/summary";
}

function createApp() {
  const app = express();

  app.disable("x-powered-by");
  app.set("trust proxy", true);

  // Observability hook: request correlation + metrics + request lifecycle logs.
  app.use(observabilityMiddleware);
  app.use(express.json({ limit: "1mb" }));
  app.use(timeoutGuard);
  app.use((req, res, next) => {
    if (isMonitoringRoute(req.path)) {
      return next();
    }
    return rateLimiter(req, res, next);
  });

  app.use((req, res, next) => {
    if (!jobManager.isAcceptingJobs() && req.method === "POST" && req.path === "/audit") {
      return res.status(503).json(formatError("Server is shutting down", "SERVICE_UNAVAILABLE"));
    }
    return next();
  });

  app.use(auditRoutes);
  app.use(resultsRoutes);
  app.use(healthRoutes);
  app.use(monitoringRoutes);

  app.use((req, res) => {
    res.status(404).json(formatError("Route not found", "ROUTE_NOT_FOUND"));
  });

  app.use(errorHandler);

  return app;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForRunningJobs(timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (jobManager.getStats().running === 0) {
      return;
    }
    await sleep(200);
  }
}

function startServer() {
  registerProcessErrorHandlers();

  const app = createApp();
  const server = app.listen(config.PORT, () => {
    log("info", "server_started", {
      port: config.PORT,
      node_env: config.NODE_ENV,
    });
  });

  let shuttingDown = false;

  const shutdown = async (signal) => {
    if (shuttingDown) {
      return;
    }
    shuttingDown = true;

    log("warn", "shutdown_requested", {
      signal,
    });

    jobManager.setAcceptingJobs(false);

    server.close(async () => {
      await waitForRunningJobs(10000);
      process.exit(0);
    });

    const hardStop = setTimeout(() => {
      process.exit(0);
    }, 11000);
    hardStop.unref();
  };

  process.on("SIGINT", () => {
    void shutdown("SIGINT");
  });

  process.on("SIGTERM", () => {
    void shutdown("SIGTERM");
  });

  return { app, server };
}

if (require.main === module) {
  startServer();
}

module.exports = {
  createApp,
  startServer,
};
