const MAX_DURATION_SAMPLES = 50;

function freshState() {
  return {
    counters: {
      total_requests: 0,
      total_audits: 0,
      successful_audits: 0,
      failed_audits: 0,
      timeout_audits: 0,
    },
    gauges: {
      active_jobs: 0,
      queued_jobs: 0,
    },
    timings: {
      execution_durations: [],
    },
  };
}

let state = freshState();

function clampGauge(value) {
  return Math.max(0, Number.isFinite(value) ? value : 0);
}

function average(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return 0;
  }

  const total = values.reduce((sum, current) => sum + current, 0);
  return Math.round((total / values.length) * 100) / 100;
}

const metrics = {
  get counters() {
    return { ...state.counters };
  },

  get gauges() {
    return { ...state.gauges };
  },

  get timings() {
    return {
      execution_durations: [...state.timings.execution_durations],
      avg_execution_time: average(state.timings.execution_durations),
    };
  },

  incrementTotalRequests() {
    state.counters.total_requests += 1;
  },

  markJobQueued() {
    state.counters.total_audits += 1;
    state.gauges.queued_jobs += 1;
  },

  markJobStarted() {
    state.gauges.queued_jobs = clampGauge(state.gauges.queued_jobs - 1);
    state.gauges.active_jobs += 1;
  },

  markJobCompleted() {
    state.counters.successful_audits += 1;
    state.gauges.active_jobs = clampGauge(state.gauges.active_jobs - 1);
  },

  markJobFailed() {
    state.counters.failed_audits += 1;
    state.gauges.active_jobs = clampGauge(state.gauges.active_jobs - 1);
  },

  markJobTimeout() {
    state.counters.timeout_audits += 1;
    state.gauges.active_jobs = clampGauge(state.gauges.active_jobs - 1);
  },

  recordExecutionDuration(durationMs) {
    const parsed = Number(durationMs);
    if (!Number.isFinite(parsed) || parsed < 0) {
      return;
    }

    state.timings.execution_durations.push(Math.round(parsed));
    if (state.timings.execution_durations.length > MAX_DURATION_SAMPLES) {
      state.timings.execution_durations.splice(
        0,
        state.timings.execution_durations.length - MAX_DURATION_SAMPLES,
      );
    }
  },

  getSuccessRate() {
    const totalAudits = state.counters.total_audits;
    if (totalAudits === 0) {
      return 0;
    }
    return Number((state.counters.successful_audits / totalAudits).toFixed(4));
  },

  getSnapshot() {
    return {
      counters: this.counters,
      gauges: this.gauges,
      timings: this.timings,
      success_rate: this.getSuccessRate(),
    };
  },

  reset() {
    state = freshState();
  },
};

module.exports = {
  metrics,
};