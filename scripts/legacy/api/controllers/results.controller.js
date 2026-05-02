const auditService = require("../services/auditService");
const { JOB_STATUS } = require("../models/job.model");
const { formatResponse, formatError } = require("./responseFormatter");

async function getResults(req, res, next) {
  try {
    const { job_id: jobId } = req.params;
    const job = auditService.getJobResult(jobId);

    if (!job) {
      return res.status(404).json(formatError("Job not found", "JOB_NOT_FOUND"));
    }

    if (job.status !== JOB_STATUS.COMPLETED) {
      return res.status(409).json(
        formatError(
          "Audit not yet complete",
          "RESULT_NOT_READY",
          {
            job_id: job.id,
            status: job.status,
            progress: job.progress,
          },
        ),
      );
    }

    if (!job.result || typeof job.result !== "object") {
      return res
        .status(500)
        .json(formatError("Completed job has no result payload", "INVALID_JOB_RESULT_STATE"));
    }

    return res.status(200).json(formatResponse(job.result));
  } catch (error) {
    return next(error);
  }
}

module.exports = {
  getResults,
};
