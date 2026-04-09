function requestLogger(req, res, next) {
  const startedAt = process.hrtime.bigint();

  res.on("finish", () => {
    const elapsedNs = process.hrtime.bigint() - startedAt;
    const durationMs = Number(elapsedNs / BigInt(1000000));

    const payload = {
      timestamp: new Date().toISOString(),
      method: req.method,
      path: req.originalUrl,
      status: res.statusCode,
      duration_ms: durationMs,
      job_id: res.locals.job_id || req.params?.job_id || null,
      ip: req.ip,
    };

    console.log(JSON.stringify(payload));
  });

  next();
}

module.exports = requestLogger;
