const path = require("path");
const dotenv = require("dotenv");

dotenv.config();

function parsePositiveInt(name, fallback) {
  const raw = process.env[name];
  const parsed = Number.parseInt(String(raw ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

const config = Object.freeze({
  NODE_ENV: process.env.NODE_ENV || "development",
  PORT: parsePositiveInt("PORT", 3000),
  LOG_LEVEL: process.env.LOG_LEVEL || "info",
  VERSION: process.env.API_VERSION || "1.0.0",

  AUDIT_TIMEOUT_MS: parsePositiveInt("AUDIT_TIMEOUT_MS", 180000),
  REQUEST_TIMEOUT_MS: parsePositiveInt("REQUEST_TIMEOUT_MS", 30000),

  RATE_LIMIT_MAX: parsePositiveInt("RATE_LIMIT_MAX", 5),
  RATE_LIMIT_WINDOW_MS: parsePositiveInt("RATE_LIMIT_WINDOW_MS", 60000),

  MAX_URL_LENGTH: parsePositiveInt("MAX_URL_LENGTH", 2048),
  DEFAULT_AUDIT_MODE: (process.env.DEFAULT_AUDIT_MODE || "balanced").toLowerCase(),

  ENGINE_PYTHON_CMD: process.env.ENGINE_PYTHON_CMD || "python",
  ENGINE_RUNNER_PATH:
    process.env.ENGINE_RUNNER_PATH || path.join("api", "services", "run_beacon_audit.py"),
});

module.exports = config;
