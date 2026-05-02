const config = require("../../config");
const jobManager = require("../../jobs/jobManager");
const { formatResponse } = require("./responseFormatter");
const { metrics } = require("../utils/metrics");

async function getHealth(req, res) {
  const stats = jobManager.getStats();
  const snapshot = metrics.getSnapshot();
  const uptimeSeconds = Math.floor(process.uptime());

  return res.status(200).json(
    formatResponse({
      status: "ok",
      uptime_s: uptimeSeconds,
      uptime_seconds: uptimeSeconds,
      active_jobs: snapshot.gauges.active_jobs,
      jobs: stats,
      version: config.VERSION,
      timestamp: new Date().toISOString(),
    }),
  );
}

module.exports = {
  getHealth,
};
