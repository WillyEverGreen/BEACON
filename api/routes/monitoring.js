const express = require("express");
const { getHealth } = require("../controllers/health.controller");
const { metrics } = require("../utils/metrics");

const router = express.Router();

router.get("/health", getHealth);

router.get("/metrics", (req, res) => {
  try {
    const snapshot = metrics.getSnapshot();

    return res.status(200).json({
      total_requests: snapshot.counters.total_requests,
      total_audits: snapshot.counters.total_audits,
      success_rate: snapshot.success_rate,
      avg_execution_time_ms: snapshot.timings.avg_execution_time,
      active_jobs: snapshot.gauges.active_jobs,
      queued_jobs: snapshot.gauges.queued_jobs,
    });
  } catch (error) {
    return res.status(500).json({
      error: {
        code: "MONITORING_METRICS_ERROR",
        message: error?.message || "Failed to collect metrics",
      },
    });
  }
});

router.get("/jobs/summary", (req, res) => {
  try {
    const snapshot = metrics.getSnapshot();

    return res.status(200).json({
      queued: snapshot.gauges.queued_jobs,
      running: snapshot.gauges.active_jobs,
      completed: snapshot.counters.successful_audits,
      failed: snapshot.counters.failed_audits,
      timeout: snapshot.counters.timeout_audits,
    });
  } catch (error) {
    return res.status(500).json({
      error: {
        code: "MONITORING_SUMMARY_ERROR",
        message: error?.message || "Failed to collect jobs summary",
      },
    });
  }
});

module.exports = router;