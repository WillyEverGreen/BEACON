const { spawn } = require("child_process");
const path = require("path");
const config = require("../../config");

function parseJsonFromMixedOutput(output) {
  const lines = String(output || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try {
      return JSON.parse(lines[index]);
    } catch {
      // Keep scanning previous lines until we find JSON payload.
    }
  }

  throw new Error("No JSON payload was found in engine output");
}

function invokeBeaconAudit({ url, mode }) {
  return new Promise((resolve, reject) => {
    const scriptPath = path.resolve(config.ENGINE_RUNNER_PATH);

    const child = spawn(config.ENGINE_PYTHON_CMD, [scriptPath, url, mode], {
      cwd: process.cwd(),
      env: {
        ...process.env,
        PYTHONPATH: process.cwd(),
      },
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", (error) => {
      const wrapped = new Error(`Engine process spawn failed: ${error.message}`);
      wrapped.code = "ENGINE_EXECUTION_FAILED";
      reject(wrapped);
    });

    child.on("close", (code) => {
      if (code !== 0) {
        const wrapped = new Error(
          `Engine process failed with code ${code}: ${(stderr || stdout).trim() || "Unknown engine error"}`,
        );
        wrapped.code = "ENGINE_EXECUTION_FAILED";
        reject(wrapped);
        return;
      }

      try {
        const payload = parseJsonFromMixedOutput(stdout);
        if (payload && payload.__error__) {
          const wrapped = new Error(String(payload.__error__));
          wrapped.code = "ENGINE_EXECUTION_FAILED";
          reject(wrapped);
          return;
        }

        resolve(payload);
      } catch (error) {
        const wrapped = new Error(`Invalid engine response: ${error.message}`);
        wrapped.code = "INVALID_ENGINE_RESPONSE";
        reject(wrapped);
      }
    });
  });
}

module.exports = {
  invokeBeaconAudit,
};
