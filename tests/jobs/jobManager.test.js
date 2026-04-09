const jobManager = require("../../jobs/jobManager");
const { JOB_STATUS } = require("../../api/models/job.model");

describe("jobManager", () => {
  beforeEach(() => {
    jobManager.clearJobs();
    jobManager.setAcceptingJobs(true);
  });

  test("creates and retrieves a job", () => {
    const job = jobManager.createJob("https://example.com", "balanced", "127.0.0.1");

    expect(job.id).toBeTruthy();
    expect(job.status).toBe(JOB_STATUS.QUEUED);

    const fetched = jobManager.getJob(job.id);
    expect(fetched).not.toBeNull();
    expect(fetched.url).toBe("https://example.com");
  });

  test("updates job using shallow merge", () => {
    const job = jobManager.createJob("https://example.com", "fast", "127.0.0.1");

    const updated = jobManager.updateJob(job.id, {
      status: JOB_STATUS.RUNNING,
      progress: 25,
      error: null,
    });

    expect(updated.status).toBe(JOB_STATUS.RUNNING);
    expect(updated.progress).toBe(25);
    expect(updated.url).toBe("https://example.com");
  });

  test("lists jobs by filter", () => {
    const one = jobManager.createJob("https://a.com", "fast", "1.1.1.1");
    const two = jobManager.createJob("https://b.com", "deep", "1.1.1.1");

    jobManager.updateJob(two.id, { status: JOB_STATUS.RUNNING });

    const queued = jobManager.listJobs({ status: JOB_STATUS.QUEUED });
    expect(queued).toHaveLength(1);
    expect(queued[0].id).toBe(one.id);
  });

  test("aggregates stats with timeout counted as failed", () => {
    const queued = jobManager.createJob("https://a.com", "fast", "1.1.1.1");
    const running = jobManager.createJob("https://b.com", "fast", "1.1.1.1");
    const completed = jobManager.createJob("https://c.com", "fast", "1.1.1.1");
    const timeout = jobManager.createJob("https://d.com", "fast", "1.1.1.1");

    jobManager.updateJob(running.id, { status: JOB_STATUS.RUNNING });
    jobManager.updateJob(completed.id, { status: JOB_STATUS.COMPLETED });
    jobManager.updateJob(timeout.id, { status: JOB_STATUS.TIMEOUT });

    const stats = jobManager.getStats();

    expect(stats).toEqual({
      queued: 1,
      running: 1,
      completed: 1,
      failed: 1,
    });

    expect(queued.status).toBe(JOB_STATUS.QUEUED);
  });
});
