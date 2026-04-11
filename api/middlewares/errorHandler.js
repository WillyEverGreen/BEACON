const { formatError } = require("../controllers/responseFormatter");
const { log } = require("../utils/logger");

function errorHandler(err, req, res, next) {
  if (res.headersSent) {
    return next(err);
  }

  const statusCode = Number.isInteger(err?.statusCode) ? err.statusCode : 500;
  const errorCode = typeof err?.code === "string" ? err.code : "INTERNAL_SERVER_ERROR";

  const logPayload = {
    request_id: req.request_id || res.locals?.request_id || null,
    job_id: res.locals?.job_id || req.params?.job_id || null,
    method: req.method,
    path: req.originalUrl,
    status_code: statusCode,
    code: errorCode,
    message: err?.message || "Unhandled error",
    stack: err?.stack || null,
  };

  log("error", "internal_error", logPayload);

  const isProduction = String(process.env.NODE_ENV || "development").toLowerCase() === "production";
  const safeMessage =
    statusCode >= 500 && isProduction ? "Internal server error" : err?.message || "Internal server error";

  return res.status(statusCode).json(formatError(safeMessage, errorCode));
}

module.exports = errorHandler;
