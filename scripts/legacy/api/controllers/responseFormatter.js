function formatResponse(data) {
  return {
    success: true,
    data,
    error: null,
  };
}

function formatError(message, code, data = null, meta = {}) {
  return {
    success: false,
    data,
    error: {
      message,
      code,
      ...meta,
    },
  };
}

module.exports = {
  formatResponse,
  formatError,
};
