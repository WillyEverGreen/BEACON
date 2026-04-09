const auditService = require("../services/auditService");
const { validateAuditRequest } = require("../services/validationService");
const { formatResponse, formatError } = require("./responseFormatter");

function selectErrorStatus(code) {
  if (code === "INVALID_MODE" || code === "BLOCKED_HOST") {
    return 422;
  }
  return 400;
}

async function enqueueAudit(req, res, next) {
  try {
    const validation = validateAuditRequest(req.body || {});
    if (!validation.valid) {
      const first = validation.errors[0] || {
        message: "Invalid request",
        code: "INVALID_REQUEST",
      };
      return res.status(selectErrorStatus(first.code)).json(formatError(first.message, first.code));
    }

    const { url, mode } = validation.normalized;
    const job = auditService.enqueueAuditJob(url, mode, req.ip);
    res.locals.job_id = job.id;

    return res.status(202).json(
      formatResponse({
        job_id: job.id,
        status: job.status,
        mode: job.mode,
        url: job.url,
        queued_at: job.queued_at.toISOString(),
        poll_url: `/audit/${job.id}`,
      }),
    );
  } catch (error) {
    if (error?.code === "SERVICE_UNAVAILABLE") {
      return res
        .status(503)
        .json(formatError("Server is shutting down and cannot accept new jobs", "SERVICE_UNAVAILABLE"));
    }
    return next(error);
  }
}

async function getAuditStatus(req, res, next) {
  try {
    const { job_id: jobId } = req.params;
    const job = auditService.getJobStatus(jobId);

    if (!job) {
      return res.status(404).json(formatError("Job not found", "JOB_NOT_FOUND"));
    }

    return res.status(200).json(formatResponse(job));
  } catch (error) {
    return next(error);
  }
}

module.exports = {
  enqueueAudit,
  getAuditStatus,
};
