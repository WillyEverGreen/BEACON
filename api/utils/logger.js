const SENSITIVE_FIELD_PATTERN = /token|password|secret|authorization|cookie|api[_-]?key|session|raw_html|html|payload|body/i;

function normalizeLevel(level) {
  const value = String(level || "info").toLowerCase();
  if (value === "warn" || value === "error" || value === "info") {
    return value;
  }
  return "info";
}

function sanitizeMetaValue(value, depth = 0) {
  if (depth > 4) {
    return "[TRUNCATED]";
  }

  if (value === null || value === undefined) {
    return value;
  }

  if (Array.isArray(value)) {
    return value.slice(0, 30).map((item) => sanitizeMetaValue(item, depth + 1));
  }

  if (typeof value === "object") {
    const clean = {};
    for (const [key, nested] of Object.entries(value)) {
      if (SENSITIVE_FIELD_PATTERN.test(key)) {
        clean[key] = "[REDACTED]";
        continue;
      }
      clean[key] = sanitizeMetaValue(nested, depth + 1);
    }
    return clean;
  }

  if (typeof value === "string" && value.length > 2000) {
    return `${value.slice(0, 2000)}...[TRUNCATED]`;
  }

  return value;
}

function normalizeMeta(meta) {
  if (!meta || typeof meta !== "object") {
    return {
      request_id: null,
      job_id: null,
      duration_ms: null,
      meta: {},
    };
  }

  const clone = { ...meta };

  const requestId = clone.request_id || clone.requestId || null;
  const jobId = clone.job_id || clone.jobId || null;
  const durationValue = Number(clone.duration_ms ?? clone.durationMs);
  const durationMs = Number.isFinite(durationValue) ? Math.max(0, Math.round(durationValue)) : null;

  delete clone.request_id;
  delete clone.requestId;
  delete clone.job_id;
  delete clone.jobId;
  delete clone.duration_ms;
  delete clone.durationMs;

  return {
    request_id: requestId,
    job_id: jobId,
    duration_ms: durationMs,
    meta: sanitizeMetaValue(clone),
  };
}

function log(level, event, meta = {}) {
  try {
    const normalizedLevel = normalizeLevel(level);
    const normalizedMeta = normalizeMeta(meta);

    const payload = {
      timestamp: new Date().toISOString(),
      level: normalizedLevel,
      event: String(event || "unknown_event"),
      request_id: normalizedMeta.request_id,
      job_id: normalizedMeta.job_id,
      duration_ms: normalizedMeta.duration_ms,
      meta: normalizedMeta.meta,
    };

    const line = JSON.stringify(payload);
    if (normalizedLevel === "error") {
      console.error(line);
      return;
    }

    console.log(line);
  } catch {
    // Logging must never interrupt request or job execution.
  }
}

module.exports = {
  log,
};