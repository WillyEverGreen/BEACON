function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function loadAuditService(timeoutMs = 300) {
  jest.resetModules();
  process.env.AUDIT_TIMEOUT_MS = String(timeoutMs);
  process.env.DEFAULT_AUDIT_MODE = "balanced";

  const jobManager = require("../../jobs/jobManager");
  jobManager.clearJobs();
  jobManager.setAcceptingJobs(true);

  const auditService = require("../../api/services/auditService");
  return { auditService, jobManager };
}

describe("auditService", () => {
  test("transitions queued -> running -> completed", async () => {
    const { auditService } = loadAuditService(500);

    auditService.__setEngineExecutor(
      () =>
        new Promise((resolve) => {
          setTimeout(() => {
            resolve({ score: 88, issues: [], pages_audited: 1 });
          }, 60);
        }),
    );

    const job = auditService.enqueueAuditJob("https://example.com", "balanced", "1.1.1.1");

    const immediate = auditService.getJobStatus(job.id);
    expect(immediate.status).toBe("queued");

    await sleep(20);
    const running = auditService.getJobStatus(job.id);
    expect(["queued", "running"]).toContain(running.status);

    await sleep(80);
    const done = auditService.getJobStatus(job.id);
    expect(done.status).toBe("completed");
    expect(done.progress).toBe(100);

    auditService.__resetEngineExecutor();
  });

  test("transitions job to timeout when engine runs too long", async () => {
    const { auditService } = loadAuditService(50);

    auditService.__setEngineExecutor(
      () =>
        new Promise((resolve) => {
          setTimeout(() => resolve({ score: 90, issues: [] }), 200);
        }),
    );

    const job = auditService.enqueueAuditJob("https://example.com", "fast", "1.1.1.1");

    await sleep(90);
    const timedOut = auditService.getJobStatus(job.id);
    expect(timedOut.status).toBe("timeout");
    expect(timedOut.error).toContain("Audit exceeded");

    auditService.__resetEngineExecutor();
  });

  test("marks failed on engine exception", async () => {
    const { auditService } = loadAuditService(200);

    auditService.__setEngineExecutor(async () => {
      throw new Error("engine exploded");
    });

    const job = auditService.enqueueAuditJob("https://example.com", "fast", "1.1.1.1");

    await sleep(20);
    const failed = auditService.getJobStatus(job.id);
    expect(failed.status).toBe("failed");
    expect(failed.error).toContain("engine exploded");

    auditService.__resetEngineExecutor();
  });

  test("marks failed on invalid engine response shape", async () => {
    const { auditService } = loadAuditService(200);

    auditService.__setEngineExecutor(async () => "not-an-object");

    const job = auditService.enqueueAuditJob("https://example.com", "deep", "1.1.1.1");

    await sleep(20);
    const failed = auditService.getJobStatus(job.id);
    expect(failed.status).toBe("failed");
    expect(failed.error).toContain("INVALID_ENGINE_RESPONSE");

    auditService.__resetEngineExecutor();
  });
});
