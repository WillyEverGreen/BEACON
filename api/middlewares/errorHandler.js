const { formatError } = require("../controllers/responseFormatter");

function errorHandler(err, req, res, next) {
  if (res.headersSent) {
    return next(err);
  }

  const statusCode = Number.isInteger(err?.statusCode) ? err.statusCode : 500;
  const errorCode = typeof err?.code === "string" ? err.code : "INTERNAL_SERVER_ERROR";

  const logPayload = {
    timestamp: new Date().toISOString(),
    level: "error",
    method: req.method,
    path: req.originalUrl,
    code: errorCode,
    message: err?.message || "Unhandled error",
    stack: err?.stack || null,
  };

  console.error(JSON.stringify(logPayload));

  const isProduction = String(process.env.NODE_ENV || "development").toLowerCase() === "production";
  const safeMessage =
    statusCode >= 500 && isProduction ? "Internal server error" : err?.message || "Internal server error";

  return res.status(statusCode).json(formatError(safeMessage, errorCode));
}

module.exports = errorHandler;
