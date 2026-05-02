const config = require("../../config");
const jobManager = require("../../jobs/jobManager");
const { JOB_STATUS } = require("../models/job.model");
const { invokeBeaconAudit } = require("./beaconEngineClient");
const { log } = require("../utils/logger");
const { metrics } = require("../utils/metrics");

let engineExecutor = invokeBeaconAudit;

function toIso(value) {
  if (!value) {
    return null;
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  return String(value);
}

function safeErrorMessage(error) {
  if (!error) {
    return "Unknown execution error";
  }

  const candidate = typeof error === "string" ? error : error.message || String(error);
  const firstLine = String(candidate).split("\n")[0].trim();
  return firstLine || "Unknown execution error";
}

function deriveGrade(score) {
  if (score >= 90) return "A";
  if (score >= 80) return "B";
  if (score >= 70) return "C";
  if (score >= 60) return "D";
  return "F";
}

function deriveRiskScore(raw, score) {
  if (Number.isFinite(Number(raw?.risk_score))) {
    return Math.max(0, Math.min(100, Math.round(Number(raw.risk_score))));
  }

  const issues = Array.isArray(raw?.issues) ? raw.issues : [];
  if (issues.length === 0) {
    return Math.max(0, Math.min(100, Math.round(100 - score)));
  }

  const weightBySeverity = {
    critical: 100,
    serious: 75,
    moderate: 45,
    minor: 20,
  };

  const totalWeight = issues.reduce((sum, issue) => {
    const key = String(issue?.severity || "moderate").toLowerCase();
    return sum + (weightBySeverity[key] || 45);
  }, 0);

  const normalized = Math.round(totalWeight / issues.length);
  return Math.max(0, Math.min(100, normalized));
}

function deriveFixes(issues) {
  const fixes = [];
  const seen = new Set();

  for (const issue of issues) {
    const fixText = String(issue?.suggested_fix || "").trim();
    if (!fixText) {
      continue;
    }

    const key = `${issue?.rule_id || "unknown"}:${fixText}`;
    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    fixes.push({
      rule_id: issue?.rule_id || "unknown",
      suggested_fix: fixText,
      code_fix: issue?.code_fix || "",
      fix_effort: issue?.fix_effort || "unknown",
    });
  }

  return fixes;
}

function deriveSuccessRate(raw) {
  if (Number.isFinite(Number(raw?.success_rate))) {
    return Number(raw.success_rate);
  }

  if (raw?.degraded_mode) {
    return 0.75;
  }

  return 1.0;
}

function assertEngineResultShape(raw) {
  if (!raw || typeof raw !== "object") {
    const error = new Error("Engine result must be an object");
    error.code = "INVALID_ENGINE_RESPONSE";
    throw error;
  }

  if (!Array.isArray(raw.issues)) {
    const error = new Error("Engine result must include an issues array");
    error.code = "INVALID_ENGINE_RESPONSE";
    throw error;
  }

  if (!Number.isFinite(Number(raw.score ?? raw.overall_score))) {
    const error = new Error("Engine result must include a numeric score");
    error.code = "INVALID_ENGINE_RESPONSE";
    throw error;
  }
}

function normalizeEngineResult(job, raw) {
  assertEngineResultShape(raw);

  const score = Number(raw.overall_score ?? raw.score);
  const riskScore = deriveRiskScore(raw, score);
  const issues = Array.isArray(raw.issues) ? raw.issues : [];
  const priorities = Array.isArray(raw.priority_ranking)
    ? raw.priority_ranking
    : Array.isArray(raw.prioritized_issues)
      ? raw.prioritized_issues
      : [];

  const pagesScanned = Number.isFinite(Number(raw.pages_audited))
    ? Number(raw.pages_audited)
    : Number.isFinite(Number(raw.pages_scanned))
      ? Number(raw.pages_scanned)
      : 1;

  const partial = Boolean(
    raw.partial ||
      raw.degraded_mode ||
      (raw.enrichment_status && String(raw.enrichment_status).toLowerCase() !== "complete"),
  );

  return {
    job_id: job.id,
    url: job.url,
    mode: job.mode,
    score: Math.round(score),
    risk_score: riskScore,
    grade: deriveGrade(score),
    issues,
    priorities,
    fixes: deriveFixes(issues),
    pages_scanned: pagesScanned,
    success_rate: deriveSuccessRate(raw),
    completed_at: new Date().toISOString(),
    partial,
  };
}

function createTimeoutPromise(timeoutMs) {
  return new Promise((_, reject) => {
    const timer = setTimeout(() => {
      const error = new Error(`Audit exceeded ${timeoutMs}ms timeout`);
      error.code = "AUDIT_TIMEOUT";
      reject(error);
    }, timeoutMs);

    timer.unref();
  });
}

function queueProgressMilestones(jobId) {
  const checkpoints = [
    [25, 100],
    [50, 400],
    [75, 900],
    [90, 1400],
  ];

  for (const [progress, delayMs] of checkpoints) {
    const timer = setTimeout(() => {
      const job = jobManager.getJob(jobId);
      if (!job || job.status !== JOB_STATUS.RUNNING) {
        return;
      }
      if (job.progress >= progress) {
        return;
      }
      jobManager.updateJob(jobId, { progress });
    }, delayMs);

    timer.unref();
  }
}

async function executeAuditJob(jobId) {
  const queued = jobManager.getJob(jobId);
  if (!queued || queued.status !== JOB_STATUS.QUEUED) {
    return;
  }

  const requestId = queued.request_id || null;

  jobManager.updateJob(jobId, {
    status: JOB_STATUS.RUNNING,
    started_at: new Date(),
    progress: 10,
  });

  queueProgressMilestones(jobId);

  // Observability hook: track engine execution start and duration.
  const executionStartedAt = Date.now();
  log("info", "engine_started", {
    request_id: requestId,
    job_id: jobId,
    mode: queued.mode,
    url: queued.url,
  });

  try {
    const result = await Promise.race([
      engineExecutor({
        url: queued.url,
        mode: queued.mode,
        jobId,
        requestId,
      }),
      createTimeoutPromise(config.AUDIT_TIMEOUT_MS),
    ]);

    const durationMs = Date.now() - executionStartedAt;
    metrics.recordExecutionDuration(durationMs);
    log("info", "engine_completed", {
      request_id: requestId,
      job_id: jobId,
      duration_ms: durationMs,
    });

    const normalized = normalizeEngineResult(queued, result);

    jobManager.updateJob(jobId, {
      status: JOB_STATUS.COMPLETED,
      completed_at: new Date(),
      progress: 100,
      result: normalized,
      error: null,
    });
  } catch (error) {
    const durationMs = Date.now() - executionStartedAt;
    metrics.recordExecutionDuration(durationMs);

    if (error && error.code === "AUDIT_TIMEOUT") {
      log("error", "engine_failed", {
        request_id: requestId,
        job_id: jobId,
        duration_ms: durationMs,
        code: error.code,
        message: safeErrorMessage(error),
      });

      jobManager.updateJob(jobId, {
        status: JOB_STATUS.TIMEOUT,
        completed_at: new Date(),
        progress: 100,
        error: safeErrorMessage(error),
      });
      return;
    }

    const safeError = safeErrorMessage(error);
    const code = error?.code ? String(error.code) : "AUDIT_EXECUTION_FAILED";

    log("error", "engine_failed", {
      request_id: requestId,
      job_id: jobId,
      duration_ms: durationMs,
      code,
      message: safeError,
    });

    jobManager.updateJob(jobId, {
      status: JOB_STATUS.FAILED,
      completed_at: new Date(),
      progress: 100,
      error: `${code}: ${safeError}`,
    });
  }
}

function enqueueAuditJob(url, mode, ip, requestId = null) {
  const job = jobManager.createJob(url, mode, ip, { requestId });
  setImmediate(() => {
    void executeAuditJob(job.id);
  });
  return job;
}

function serializeJob(job) {
  if (!job) {
    return null;
  }

  return {
    job_id: job.id,
    status: job.status,
    progress: job.progress,
    mode: job.mode,
    url: job.url,
    queued_at: toIso(job.queued_at),
    started_at: toIso(job.started_at),
    completed_at: toIso(job.completed_at),
    error: job.error,
  };
}

function getJobStatus(jobId) {
  const job = jobManager.getJob(jobId);
  return serializeJob(job);
}

function getJobResult(jobId) {
  return jobManager.getJob(jobId);
}

function __setEngineExecutor(mockExecutor) {
  engineExecutor = mockExecutor;
}

function __resetEngineExecutor() {
  engineExecutor = invokeBeaconAudit;
}

module.exports = {
  enqueueAuditJob,
  getJobStatus,
  getJobResult,
  __setEngineExecutor,
  __resetEngineExecutor,
};
