const { JOB_STATUS, createJobRecord } = require("../api/models/job.model");

const jobs = new Map();
let acceptingJobs = true;

function createJob(url, mode, ip) {
  if (!acceptingJobs) {
    const error = new Error("Server is shutting down and not accepting new jobs");
    error.code = "SERVICE_UNAVAILABLE";
    throw error;
  }

  const job = createJobRecord({ url, mode, ip });
  jobs.set(job.id, job);
  return job;
}

function getJob(jobId) {
  return jobs.get(jobId) || null;
}

function updateJob(jobId, patch) {
  const current = getJob(jobId);
  if (!current) {
    return null;
  }

  const next = { ...current, ...patch };
  jobs.set(jobId, next);
  return next;
}

function listJobs(filter = {}) {
  const entries = Array.from(jobs.values());
  if (!filter || Object.keys(filter).length === 0) {
    return entries;
  }

  return entries.filter((job) =>
    Object.entries(filter).every(([key, value]) => job[key] === value),
  );
}

function getStats() {
  let queued = 0;
  let running = 0;
  let completed = 0;
  let failed = 0;

  for (const job of jobs.values()) {
    if (job.status === JOB_STATUS.QUEUED) {
      queued += 1;
      continue;
    }
    if (job.status === JOB_STATUS.RUNNING) {
      running += 1;
      continue;
    }
    if (job.status === JOB_STATUS.COMPLETED) {
      completed += 1;
      continue;
    }
    if (job.status === JOB_STATUS.FAILED || job.status === JOB_STATUS.TIMEOUT) {
      failed += 1;
    }
  }

  return { queued, running, completed, failed };
}

function setAcceptingJobs(enabled) {
  acceptingJobs = Boolean(enabled);
}

function isAcceptingJobs() {
  return acceptingJobs;
}

function clearJobs() {
  jobs.clear();
}

module.exports = {
  createJob,
  getJob,
  updateJob,
  listJobs,
  getStats,
  setAcceptingJobs,
  isAcceptingJobs,
  clearJobs,
};
