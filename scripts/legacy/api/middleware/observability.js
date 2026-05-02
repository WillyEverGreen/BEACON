const crypto = require("crypto");
const { log } = require("../utils/logger");
const { metrics } = require("../utils/metrics");

let processHandlersRegistered = false;

function createRequestId() {
  try {
    return `req_${crypto.randomUUID().replace(/-/g, "").slice(0, 16)}`;
  } catch {
    const fallback = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
    return `req_${fallback}`;
  }
}

function observabilityMiddleware(req, res, next) {
  const startedAt = Date.now();
  const requestId = createRequestId();

  req.request_id = requestId;
  res.locals.request_id = requestId;

  try {
    metrics.incrementTotalRequests();
    log("info", "request_received", {
      request_id: requestId,
      method: req.method,
      path: req.originalUrl,
      ip: req.ip,
    });
  } catch {
    // Metrics/logging failures should not interrupt request processing.
  }

  res.on("finish", () => {
    try {
      const durationMs = Date.now() - startedAt;
      const jobId = res.locals.job_id || req.params?.job_id || null;
      const failed = res.statusCode >= 400;

      log(failed ? "error" : "info", failed ? "request_failed" : "request_completed", {
        request_id: requestId,
        job_id: jobId,
        duration_ms: durationMs,
        method: req.method,
        path: req.originalUrl,
        status: res.statusCode,
      });
    } catch {
      // Metrics/logging failures should not interrupt request processing.
    }
  });

  next();
}

function shouldExitOnFatal() {
  return String(process.env.NODE_ENV || "development").toLowerCase() !== "test";
}

function registerProcessErrorHandlers() {
  if (processHandlersRegistered) {
    return;
  }

  processHandlersRegistered = true;

  process.on("unhandledRejection", (reason) => {
    try {
      log("error", "unhandled_rejection", {
        reason: String(reason),
      });
    } finally {
      if (shouldExitOnFatal()) {
        process.exit(1);
      }
    }
  });

  process.on("uncaughtException", (error) => {
    try {
      log("error", "internal_error", {
        message: error?.message || "Uncaught exception",
        stack: error?.stack || null,
      });
    } finally {
      if (shouldExitOnFatal()) {
        process.exit(1);
      }
    }
  });
}

module.exports = {
  observabilityMiddleware,
  registerProcessErrorHandlers,
};