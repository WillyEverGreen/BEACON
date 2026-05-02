const config = require("../../config");
const { formatError } = require("../controllers/responseFormatter");

function timeoutGuard(req, res, next) {
  const timeout = setTimeout(() => {
    if (res.headersSent) {
      return;
    }

    res.status(504).json(formatError("Request timed out", "GATEWAY_TIMEOUT"));
  }, config.REQUEST_TIMEOUT_MS);

  timeout.unref();

  const cleanup = () => clearTimeout(timeout);
  res.on("finish", cleanup);
  res.on("close", cleanup);

  next();
}

module.exports = timeoutGuard;
