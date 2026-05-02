const config = require("../../config");
const { formatError } = require("../controllers/responseFormatter");

const buckets = new Map();

function pruneExpired(now) {
  for (const [ip, bucket] of buckets.entries()) {
    if (now - bucket.windowStart >= config.RATE_LIMIT_WINDOW_MS) {
      buckets.delete(ip);
    }
  }
}

function rateLimiter(req, res, next) {
  const now = Date.now();
  pruneExpired(now);

  const ip = req.ip || "unknown";
  const current = buckets.get(ip);
  const windowExpired = !current || now - current.windowStart >= config.RATE_LIMIT_WINDOW_MS;

  const bucket = windowExpired
    ? { count: 0, windowStart: now }
    : { ...current };

  bucket.count += 1;
  buckets.set(ip, bucket);

  if (bucket.count > config.RATE_LIMIT_MAX) {
    const retryAfterMs = Math.max(0, config.RATE_LIMIT_WINDOW_MS - (now - bucket.windowStart));
    const retryAfterSec = Math.max(1, Math.ceil(retryAfterMs / 1000));

    return res
      .status(429)
      .json(formatError("Rate limit exceeded", "RATE_LIMIT_EXCEEDED", null, { retry_after_s: retryAfterSec }));
  }

  return next();
}

function __resetRateLimiter() {
  buckets.clear();
}

module.exports = {
  rateLimiter,
  __resetRateLimiter,
};
