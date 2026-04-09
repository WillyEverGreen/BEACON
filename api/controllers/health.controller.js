const config = require("../../config");
const jobManager = require("../../jobs/jobManager");
const { formatResponse } = require("./responseFormatter");

async function getHealth(req, res) {
  const stats = jobManager.getStats();

  return res.status(200).json(
    formatResponse({
      status: "ok",
      uptime_s: Math.floor(process.uptime()),
      jobs: stats,
      version: config.VERSION,
      timestamp: new Date().toISOString(),
    }),
  );
}

module.exports = {
  getHealth,
};
