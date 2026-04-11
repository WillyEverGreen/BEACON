const { v4: uuidv4 } = require("uuid");

const JOB_STATUS = Object.freeze({
  QUEUED: "queued",
  RUNNING: "running",
  COMPLETED: "completed",
  FAILED: "failed",
  TIMEOUT: "timeout",
});

const ALLOWED_MODES = Object.freeze(["fast", "balanced", "deep"]);

function createJobRecord({ url, mode, ip, request_id = null }) {
  return {
    id: uuidv4(),
    url,
    mode,
    status: JOB_STATUS.QUEUED,
    progress: 0,
    queued_at: new Date(),
    started_at: null,
    completed_at: null,
    result: null,
    error: null,
    ip: ip || "unknown",
    request_id,
  };
}

module.exports = {
  JOB_STATUS,
  ALLOWED_MODES,
  createJobRecord,
};
